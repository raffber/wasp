from .fs import Directory, directories
from .argument import ArgumentCollection, Argument
from .metadata import Metadata
from . import log, extensions, decorators
from .util import parse_assert, FunctionDecorator
import json

CONFIG_FILE_NAMES = ['wasprc.json', 'wasprc.user.json']
"""
Default file names for config files.
"""


# TODO: document config keys and how they can be set

class ConfigKey(object):
    def __init__(self, key, parser=None, merger=None):
        self._key = key
        self._parser = parser
        self._merger = merger

    def __set__(self, instance, value):
        instance.set(self._key, value)

    def __get__(self, instance, owner):
        return instance.get(self._key)

    def parse(self, instance, value):
        if self._parser is not None:
            instance.set(self._key, self._parser(instance, value))
            return
        instance.set(self._key, value)

    def merge(self, instance, hp):
        x = hp.get(self._key)
        if x is not None:
            if self._merger:
                self._merger(instance, x)
                return
            instance.set(self._key, x)

    @property
    def key(self):
        return self._key


VALID_VERBOSITY = ['debug', 'info', 'warn', 'error', 'fatal', 'quiet']


def _parse_verbosity(instance, value):
    parse_assert(value in VALID_VERBOSITY,
                 'Invalid verbosity key. expected on of `{0}`'.format(VALID_VERBOSITY))
    value = value.lower().strip()
    ret = 3
    if value == 'debug':
        ret = 5
    elif value == 'info':
        ret = 4
    elif value == 'warn':
        ret = 3
    elif value == 'error':
        ret = 2
    elif value == 'fatal':
        ret = 1
    elif value == 'quiet':
        ret = 0
    return ret


def _merge_extensions(instance, hp):
    if instance.extension is not None:
        instance.extensions.extend(hp)
    else:
        instance.extensions = set()


def _parse_extensions(instance, lst):
    parse_assert(isinstance(lst, list), 'While parsing config file: Expected a list of string for `extensions`.')
    parse_assert(all([isinstance(x, str) for x in lst]), 'While parsing config file: '
                                                         'Expected a list of string for `extensions`.')
    return set(lst)


def _argument_merger(instance, hp):
    if instance.arguments is None:
        instance.arguments = hp
    else:
        instance.arguments.overwrite_merge(hp)


def _argument_parser(instance, d):
    parse_assert(isinstance(d, dict), 'While parsing config file: Expected a '
                                      'dictionary for key `arguments` in config file.')
    ret = ArgumentCollection()
    for key, value in d.items():
        ret[key] = Argument(key).assign(value)
    return ret


def _assert_bool(instance, v):
    parse_assert(isinstance(v, bool), 'Expected a bool, was `{0}`'.format(type(v).__name__))
    return v


def _assert_string(instance, v):
    parse_assert(isinstance(v, str), 'Expected a str, was `{0}`'.format(type(v).__name__))
    return v


class Config(object):
    """
    Collects config information and parses it from json-like datastructures.
    :param json_data: dict collecting infromation for parsing the config.
    """

    extensions = ConfigKey('extensions', parser=_parse_extensions, merger=_merge_extensions)
    metadata = ConfigKey('metadata', parser=lambda _, x: Metadata.from_json(x))
    pythonpath = ConfigKey('pythonpath', parser=lambda _, x: directories(x))
    verbosity = ConfigKey('verbosity', parser=_parse_verbosity)
    arguments = ConfigKey('arguments', parser=_argument_parser, merger=_argument_merger)
    default_command = ConfigKey('default_command', parser=_assert_string)
    pretty = ConfigKey('pretty', parser=_assert_bool)

    def __init__(self, json_data=None):
        self._values = {}
        self._handlers = {}
        for k, v in vars(self.__class__).items():
            if isinstance(v, ConfigKey):
                self._handlers[v.key] = v
        if json_data is None:
            return
        if not isinstance(json_data, dict):
            raise ValueError('Expected dict as root item of config file, got `{0}`'.format(type(json_data).__name__))
        for key, value in json_data.items():
            parse_assert(isinstance(key, str), 'While parsing config file: Expected '
                                               'string as key, got `{0}`'.format(type(key).__name__))
            if key in self._handlers:
                self._handlers[key].parse(self, value)
                continue
            # this should not happend, in this case, the user provided an invalid key.
            parse_assert(False, 'Unexpected key `{0}`'.format(key))

    def overwrite_merge(self, higher_priority):
        """
        Merges two config objects. In case both config files contain
        the same values, the values from ``higher_priority`` take precedence.
        """
        for handler in self._handlers.values():
            handler.merge(self, higher_priority)

    def get(self, key):
        return self._values.get(key, None)

    def set(self, key, value):
        assert key in self._handlers.keys()
        self._values[key] = value

    @classmethod
    def from_file(cls, fpath):
        """
        Create a new config instance from a json file. Returns an empty configuration
        upon failure.
        """
        d = None
        try:
            with open(fpath, 'r') as f:
                d = json.load(f)
        except FileNotFoundError:
            log.debug('Config file at {0} does not exist.'.format(fpath))
        try:
            config = Config(json_data=d)
        except ValueError as e:
            log.warn('Invalid config file at {0}. Ignoring. Error was:\n{1}'.format(fpath, str(e)))
            return Config()
        return config

    @classmethod
    def load_from_directory(cls, fpath, fnames=CONFIG_FILE_NAMES):
        """
        Load mulitple files from a directory referenced by ``fpath``.
        The files are loaded in the precedence they are given in ``fnames`` and
        and the resulting config objects are merged, where the last loaded
        file has precedence over the previously loaded files. Thus, config keys
        defined in wasprc.json can be overridden by wasprc.user.json.

        :param fpath: Path of the directory.
        :param fnames: List of file names to be loaded.
        """
        ret = []
        for fname in fnames:
            path = str(Directory(fpath).join(fname))
            c = cls.from_file(path)
            ret.append(c)
        config = None
        for x in ret:
            if config is None:
                config = x
                continue
            config.overwrite_merge(x)
        if config is None:
            return Config()
        return config


class config(FunctionDecorator):
    """
    Function decorator for registring config handlers.
    These functions may return a config object, which takes
    precedence over previously defined config objects.
    See ``wasp.main.load_decorator_config``.
    """

    def __init__(self, f):
        super().__init__(f)
        decorators.config.append(f)
