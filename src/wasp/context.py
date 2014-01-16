from .directory import WaspDirectory
from .options import OptionsCollection
from .cache import Cache
from .hooks import Hooks
from .node import NodeDb
from .arguments import Argument
from .execution import TaskExecutionPool, RunnableDependencyTree
from .ui import Log
from .environment import Environment
import os


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

    def __init__(self, projectname, topdir='.', builddir='build', prefix='/usr'):
        self._topdir = WaspDirectory(topdir)
        assert self._topdir.valid, 'The given topdir must exist!!'
        self._builddir = WaspDirectory(builddir)
        self._builddir.ensure_exists()
        self._cachedir = WaspDirectory(self._builddir.join('c4che'))
        assert isinstance(projectname, str), 'projectname must be a string!'
        self._projectname = projectname
        # dynamically loaded stuff:
        self._cache = Cache(self._cachedir)
        self._prefix = WaspDirectory(os.environ.get('PREFIX', prefix))
        self._options = OptionsCollection()
        self._configure_options = OptionsCollection(cache=self._cache)
        self._store = Store(self._cache)
        self._env = Environment(self._cache)
        self._commands = []
        self._nodes = NodeDb(self._cache)
        self._checks = {}
        self._log = Log()

    def store_result(self, result):
        raise NotImplementedError

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

    def configure_options(self):
        return self._configure_options

    @property
    def store(self):
        return self._store

    @property
    def checks(self):
        return self._checks

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

    def run(self):
        tree = RunnableDependencyTree(self.tasks)
        jobs = Argument('jobs').require_type(int).retrieve(self.env, self.options, default=1)
        executor = TaskExecutionPool(tree, num_jobs=int(jobs))
        return executor.run()
