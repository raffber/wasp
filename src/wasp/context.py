
from .directory import WaspDirectory
from .options import OptionsCollection
import os


class Environment(object):
    def __init__(self, cachedir):
        self._cachedir = cachedir
        self._env = dict(os.environ)
    
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
        pass

    def load_from_env(self):
        pass


class Store(object):
    def __init__(self, cachedir):
        pass


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
        self._store = Store(self.cachedir)

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

ctx = None