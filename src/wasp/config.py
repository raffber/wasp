from .fs import Directory
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


class Config(object):
    """
    Collects config information and parses it from json-like datastructures.
    :param json_data: dict collecting infromation for parsing the config.
    """

    class KeyHandler(object):
        """
        Handler for a config key. Adds a property attribute to
        ``config.__class__``. Also allows setting a parser which extracts
        the data from the JSON data structure and a merger which merges multiple
        config values.
        """
        def __init__(self, config, keyname, parser=None, merger=None):
            self._keyname = keyname
            self._parser = parser
            self._value = None
            self._merger = merger

            def getter(s):
                return s._handlers[self._keyname]._value

            def setter(s, item):
                 s._handlers[self._keyname]._value = item
            setattr(config.__class__, self._keyname, property(getter, setter))

        @property
        def name(self):
            return self._keyname

        def parse(self, value):
            if self._parser is not None:
                self._value = self._parser(value)
                return
            self._value = value

        def overwrite_merge(self, higher_priority):
            x = getattr(higher_priority, self._keyname)
            if x is not None:
                if self._merger:
                    self._merger(x)
                    return
                self._value = x

    def __init__(self, json_data=None):
        self._handlers = None
        self.populate_handlers()
        if json_data is None:
            return
        if not isinstance(json_data, dict):
            raise ValueError('Expected dict as root item of config file, got `{0}`'.format(type(json_data).__name__))
        for key, value in json_data.items():
            parse_assert(isinstance(key, str), 'While parsing config file: Expected '
                                               'string as key, got `{0}`'.format(type(key).__name__))
            if key in self._handlers:
                self._handlers[key].parse(value)
                continue
            # this should not happend, in this case, the user provided an invalid key.
            parse_assert(False, 'Unexpected key `{0}`'.format(key))

    def populate_handlers(self):
        """
        Populates self with configuration handlers.
        """
        make_handler = lambda k, parser=None, merger=None: Config.KeyHandler(self, k, parser=parser, merger=merger)
        self._handlers = {
            'extensions': make_handler('extensions', parser=self._parse_extensions, merger=self._merge_extensions),
            'metadata': make_handler('metadata', parser=lambda x: Metadata.from_json(x)),
            'pythonpath': make_handler('pythonpath', parser=lambda x: Directory(x)),
            'verbosity': make_handler('verbosity', parser=self._parse_verbosity),
            'arguments': make_handler('arguments', parser=self._argument_parser, merger=self._argument_merger),
            'default_command': make_handler('default_command'),
            'pretty': make_handler('pretty')
        }
        handlers = extensions.api.create_config_handlers()
        self._handlers.update({x.name: x for x in handlers})

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

    def overwrite_merge(self, higher_priority):
        """
        Merges two config objects. In case both config files contain
        the same values, the values from ``higher_priority`` take precedence.
        """
        for handler in self._handlers.values():
            handler.overwrite_merge(higher_priority)

    def _parse_verbosity(self, value):
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

    def _merge_extensions(self, hp):
        if self.extension is not None:
            self.extensions.extend(hp)
        else:
            self.extensions = set()

    def _parse_extensions(self, lst):
        parse_assert(isinstance(lst, list), 'While parsing config file: Expected a list of string for `extensions`.')
        parse_assert(all([isinstance(x, str) for x in lst]), 'While parsing config file: '
                                                             'Expected a list of string for `extensions`.')
        return set(lst)

    def _argument_merger(self, hp):
        self.arguments.overwrite_merge(hp)

    def _argument_parser(self, d):
        parse_assert(isinstance(d, dict), 'While parsing config file: Expected a '
                                          'dictionary for key `arguments` in config file.')
        ret = ArgumentCollection()
        for key, value in d.items():
            ret[key] = Argument(key).assign(value)
        return ret


class config(FunctionDecorator):
    """
    Function decorator for registring config handlers.
    These functions may return a config object, which takes
    precedence over previously defined config objects.
    See ``wasp.main.load_decorator_config``.
    """
    def __init__(self, f):
        decorators.config.append(f)