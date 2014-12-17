from .fs import Directory
from .argument import ArgumentCollection, Argument
from .metadata import Metadata
from . import log
from .util import parse_assert
import json

CONFIG_FILE_NAMES = ['wasprc.json', 'wasprc.user.json']


# TODO: more generic approach than what's here at the moment
# though for the time being this is probably the simplest.


class Config(object):

    class KeyHandler(object):
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
        make_handler = lambda k, parser, merger=None: Config.KeyHandler(self, k, parser=parser, merger=merger)
        self._handlers = {
            'metadata': make_handler('metadata', lambda x: Metadata.from_json(x)),
            'pythonpath': make_handler('pythonpath', lambda x: Directory(x)),
            'verbosity': make_handler('verbosity', self._parse_verbosity),
            'arguments': make_handler('arguments', self._argument_parser, merger=self._argument_merger),
        }
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
            parse_assert(False, 'Unexpected key `{0}`'.format(key))

    @classmethod
    def from_file(cls, fpath):
        d = None
        try:
            with open(fpath, 'r') as f:
                d = json.load(f)
        except FileNotFoundError:
            log.debug('Config file at {0} does not exist.'.format(fpath))
        try:
            config = Config(json_data=d)
        except ValueError:
            log.warn('Invalid config file at {0}. Ignoring.'.format(fpath))
            return Config()
        return config

    @classmethod
    def load_from_directory(cls, fpath, fnames=CONFIG_FILE_NAMES):
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
        for handler in self._handlers.values():
            handler.overwrite_merge(higher_priority)

    def keep_merge(self, lower_priority):
        raise NotImplementedError

    @property
    def arguments(self):
        return self._arguments

    @property
    def python_path(self):
        return self._python_path

    @property
    def verbosity(self):
        return self._verbosity

    def _parse_verbosity(self, value):
        value = value.lower().trim()
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

    def _argument_merger(self, hp):
        self.arguments.overwrite_merge(hp)

    def _argument_parser(self, d):
        parse_assert(isinstance(d, dict), 'While parsing config file: Expected a '
                                          'dictionary for key `arguments` in config file.')
        ret = ArgumentCollection()
        for key, value in d.items():
            ret[key] = Argument(key).assign(value)
        return ret
