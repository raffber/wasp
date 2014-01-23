from .directory import WaspDirectory
from .options import OptionsCollection
from .cache import Cache
from .node import SignatureDb, FileSignature, PreviousSignatureDb
from .arguments import Argument
from .execution import TaskExecutionPool, RunnableDependencyTree
from .ui import Log
from .environment import Environment
from .task import TaskResultCollection, PreviousTaskDb, TaskDb
import os


class Store(dict):
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

    def __init__(self, projectname, recurse_files=[], topdir='.', builddir='build', prefix='/usr'):
        # we need to get the initialization order right.
        # the simplest way to do this is to initialize things first
        # that have no dependencies
        self._log = Log()
        self._results = TaskResultCollection()
        self._checks = TaskResultCollection()
        # create the directories
        self._topdir = WaspDirectory(topdir)
        assert self._topdir.valid, 'The given topdir must exist!!'
        self._builddir = WaspDirectory(builddir)
        self._builddir.ensure_exists()
        self._cachedir = WaspDirectory(self._builddir.join('c4che'))
        self._prefix = WaspDirectory(os.environ.get('PREFIX', prefix))
        assert isinstance(projectname, str), 'projectname must be a string!'
        self._projectname = projectname
        # create the signature for this build script
        # the current build script
        fname = self._topdir.join('build.py')
        self._scripts_signatures = {fname: FileSignature(fname)}
        for fpath in recurse_files:
            self._scripts_signatures[fpath] = FileSignature(fpath)
        # create the cache
        self._cache = Cache(self._cachedir)
        # make sure to do this early on, otherwise
        # such that everything that depends on the cache
        # has valid data and does not accidently read old stuff
        self.load()
        # initialize options
        self._options = OptionsCollection()
        self._configure_options = OptionsCollection(cache=self._cache)
        self._store = Store(self._cache)
        self._env = Environment(self._cache)
        self._commands = []
        self._signatures = SignatureDb(self._cache)
        self._previous_signatures = PreviousSignatureDb(self._cache)
        self._previous_tasks = PreviousTaskDb(self._cache)
        self._tasks = TaskDb(self._cache)

    def has_changed(self, node):
        raise NotImplementedError

    @property
    def topdir(self):
        return self._topdir

    @property
    def signatures(self):
        return self._signatures

    @property
    def previous_signatures(self):
        return self._previous_signatures

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

    def save(self):
        d = self.cache.getcache('script-signatures')
        for fpath, signature in self._scripts_signatures:
            d[fpath] = signature.to_json()
        self.signatures.save()
        self.tasks.save()
        self.cache.save()

    def load(self):
        self._cache.load()
        signatures = self._cache.getcache('script-signatures')
        invalid = False
        for fpath, signature in self._scripts_signatures:
            ser_sig = signatures.get(fpath, None)
            if ser_sig is None:
                invalid = True
                # continue to see if the files have actually changed
                continue
            old_sig = FileSignature.from_json(ser_sig)
            if old_sig != signature:
                self.log.info('Build scripts have changed since last execution! Configure the project again.')
                invalid = True
                break
        if invalid:
            self.cache.clear()

    @property
    def tasks(self):
        return self._tasks

    @property
    def previous_tasks(self):
        return self._previous_tasks

    def run_tasks(self):
        tree = RunnableDependencyTree(self.tasks)
        jobs = Argument('jobs').require_type(int).retrieve(self.env, self.options, default=1)
        executor = TaskExecutionPool(tree, num_jobs=int(jobs))
        res = executor.run()
        self._tasks.clear()
        return res
