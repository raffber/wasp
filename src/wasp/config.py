from .fs import Directory
from .argument import ArgumentCollection
from .metadata import Metadata
from . import log
import json

CONFIG_FILE_NAMES = ['waprc.json', 'wasprc.user.json']


# TODO: more generic approach than what's here at the moment
# though for the time being this is probably the simplest.


class Config(object):

    def __init__(self, json_data=None):
        self._arguments = ArgumentCollection()
        self._python_path = None
        self._verbosity = None
        self._metadata = None
        if json_data is None:
            return
        if not isinstance(json_data, dict):
            raise ValueError
        for key, value in json_data.items():
            if not isinstance(key, str):
                raise ValueError
            if key == 'arguments':
                if not isinstance(value, dict):
                    raise ValueError
                self._arguments.add(**value)
            elif key == 'pythonpath':
                self._python_path = Directory(value)
            elif key == 'metadata':
                self._metadata = Metadata.from_json(value)
            elif key == 'verbosity':
                self._parse_verbosity(value)

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
            if not c.isempty():
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
        hp = higher_priority
        self._python_path = hp.python_path if hp.python_path is not None else self._python_path
        self._verbosity = hp.verbosity if hp.verbosity is not None else self._verbosity
        self._metadata = hp.metadata if hp.metadata is not None else self._metadata
        if hp.arguments is not None:
            self._arguments.overwrite_merge(hp.arguments)

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

    @property
    def metadata(self):
        return self._metadata

    def isempty(self):
        return self.arguments.isempty() or self.python_path is None or self._verbosity is None

    def _parse_verbosity(self, value):
        value = value.lower().trim()
        if value == 'debug':
            self._verbosity = 5
        elif value == 'info':
            self._verbosity = 4
        elif value == 'warn':
            self._verbosity = 3
        elif value == 'error':
            self._verbosity = 2
        elif value == 'fatal':
            self._verbosity = 1
        elif value == 'quiet':
            self._verbosity = 0

