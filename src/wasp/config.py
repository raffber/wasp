from .fs import Directory
from .argument import ArgumentCollection
from . import ctx
import json

CONFIG_FILE_NAMES = ['waprc.json', 'wasprc.user.json']


# TODO: allow setting:
# * build directory
# * project name
#

# TODO: more generic approach than what's here at the moment
# though for the time being this is probably the simplest.


class Config(object):

    def __init__(self, json_data):
        self._arguments = ArgumentCollection()
        self._python_path = None
        self._verbosity = None
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
            elif key == 'verbosity':
                self._parse_verbosity(value)

    @classmethod
    def from_file(cls, fpath):
        try:
            d = json.load(fpath)
        except ValueError:
            ctx.log.error('Invalid config file at {0}. Ignoring.' % format(fpath))
        return Config(d)

    @classmethod
    def load_from_directory(cls, fpath, fnames=CONFIG_FILE_NAMES):
        ret = []
        for fname in fnames:
            path = str(Directory(fpath).join(fname))
            c = cls.from_file(path)
            if not c.isempty():
                ret.append(c)
        return ret

    def overwrite_merge(self, higher_priority):
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

    def isempty(self):
        return self.arguments.isempty() or self.python_path is None or self.default_verbosity is None

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

