from .directory import WaspDirectory
from .options import OptionsCollection
from .cache import Cache
from .hooks import Hooks
from .node import NodeDb
import os


class Environment(object):
    def __init__(self, cache):
        self._cache = cache
        self._env = []
        self.load_from_cache()
    
    def __getitem__(self, key):
        return self._env[key]

    def __setitem__(self, key, value):
        self._env[key] = value

    def __hasitem__(self, key):
        if key in self._env:
            return True
        return False

    def get(self, key, *args):
        if key in self._env:
            return self._env[key]
        if len(args) == 0:
            return None
        return args[0]

    def load_from_cache(self):
        # copy, such that we don't change the cache
        self._env = dict(self._cache.getcache('env'))

    def load_from_env(self):
        self._env = dict(os.environ)

    def save(self):
        self._cache.setcache('env', self._env)


class Store(object):
    def __init__(self, cache):
        self._cache = cache

    def __setitem__(self, key, value):
        self._cache.set('store', key, value)

    def __getitem__(self, key):
        ret = self._cache.get('store', key)
        if ret is None:
            raise KeyError
        return ret

    def get(self, key, *args):
        if len(args) > 1:
            raise TypeError('Only one argument may be provided as default argument if "key" does not exits')
        ret = self._cache.get('store', key)
        if ret is not None:
            return ret
        if len(args) == 0:
            return None
        return args[1]


class Context(object):

    def __init__(self, topdir, builddir, projectname):
        self._topdir = WaspDirectory(topdir)
        self._builddir = WaspDirectory(builddir)
        self._cachedir = self._builddir.join('c4che')
        assert(isinstance(projectname, str), 'projectname must be a string!')
        self._projectname = projectname
        # dynamically loaded stuff:
        self._env = Environment(os.environ)
        self._prefix = WaspDirectory(os.environ.get('PREFIX', '/usr'))
        self._options = OptionsCollection(self.cachedir)
        self._store = Store(self._cache)
        self._cache = Cache(self._cachedir)
        self._commands = []
        self._hooks = Hooks()
        self._nodes = NodeDb(self._cache)

    @property
    def hooks(self):
        return self._hooks

    @property
    def topdir(self):
        return self._topdir

    @property
    def prefix(self):
        return self._prefix

    @property
    def builddir(self):
        return self._builddir

    @property
    def projectname(self):
        return self._projectname
    
    @property
    def cachedir(self):
        return self._cachedir

    @property
    def env(self):
        return self._env

    @property
    def options(self):
        return self._options

    @property
    def store(self):
        return self._store

    @property
    def commands(self):
        return self._commands

    def _recurse_single(self, d):
        raise NotImplementedError

    def recurse(self, subdirs):
        if isinstance(subdirs, str):
            self._recurse_single(subdirs)
            return
        for d in subdirs:
            self._recures_single(d)

ctx = None