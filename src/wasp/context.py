from .directory import WaspDirectory
from .options import OptionsCollection
from .cache import Cache
from .signature import SignatureProvider, FileSignature, SignatureStore
from .arguments import Argument
from .execution import TaskExecutionPool, RunnableDependencyTree
from .ui import Log
from .environment import Environment
from .task import TaskResultCollection, TaskDb
from .util import load_module_by_path
from .tools import ToolError, NoSuchToolError
from .tools import proxies
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
        self.projectname = projectname
        # create the directories
        self._topdir = WaspDirectory(topdir)
        assert self._topdir.valid, 'The given topdir must exist!!'
        self._builddir = WaspDirectory(builddir)
        self._builddir.ensure_exists()
        self._cachedir = WaspDirectory(self._builddir.join('c4che'))
        self._prefix = WaspDirectory(os.environ.get('PREFIX', prefix))
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
        self._store = Store(self._cache)
        self._env = Environment(self._cache)
        self._commands = []
        self._signatures = SignatureProvider(self._cache)
        self._previous_signatures = SignatureStore(self._cache)
        self._tasks = TaskDb(self._cache)
        self._tooldir = WaspDirectory('wasp-tools')
        self._results.load()
        self._tools = {}
        self._arguments = {}
        self._clean_files = []

    def get_tooldir(self):
        return self._tooldir

    def set_tooldir(self, tooldir):
        if isinstance(tooldir, str):
            tooldir = WaspDirectory(tooldir)
        assert isinstance(tooldir, WaspDirectory), 'tooldir must either be a path to a directory or a WaspDirectory'
        tooldir.ensure_exists()
        self._tooldir = tooldir

    tooldir = property(get_tooldir, set_tooldir)

    def load_tool(self, toolname, *args, path=None):
        if toolname in self._tools:
            ret =self._tools[toolname]
        else:
            if path is None:
                path = self._tooldir.path
            path = os.path.abspath(path)
            fpath = os.path.join(path, toolname + '.py')
            try:
                module = load_module_by_path(fpath)
                self._tools[toolname] = module
                if toolname in proxies.keys():
                    # inject the tool proxy
                    object.__setattr__(proxies[toolname], "_obj", module)
                ret = module
            except FileNotFoundError:
                raise NoSuchToolError('No such tool: {0}'.format(toolname))
        if len(args) > 0:
            ret = [ret]
        for arg in args:
            tool = self.load_tool(arg, path=path)
            ret.append(tool)
        if len(args) > 0:
            return tuple(ret)
        return ret

    def tool(self, toolname):
        assert isinstance(toolname, str), 'Toolname must be a string.'
        if not toolname in self._tools:
            raise ToolError('No such tool "{0}" loaded. Make sure to load the ' \
                'tool using load_tool() during initialization time'.format(toolname))
        return self._tools[toolname]

    @property
    def log(self):
        return self._log

    @property
    def clean_files(self):
        return self._clean_files

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
    def cachedir(self):
        return self._cachedir

    @property
    def env(self):
        return self._env

    @property
    def argumetns(self):
        return self._arguments

    @property
    def options(self):
        return self._options

    @property
    def store(self):
        return self._store

    @property
    def results(self):
        return self._results

    @property
    def commands(self):
        return self._commands

    def save(self):
        d = self.cache.getcache('script-signatures')
        for fpath, signature in self._scripts_signatures.items():
            d[fpath] = signature.to_json()
        self.signatures.save()
        self.cache.save()

    def load(self):
        self._cache.load()
        signatures = self._cache.getcache('script-signatures')
        invalid = False
        for (fpath, signature) in self._scripts_signatures.items():
            ser_sig = signatures.get(fpath, None)
            if ser_sig is None:
                invalid = True
                # continue to see if the files have actually changed
                continue
            old_sig = FileSignature(**ser_sig)
            if old_sig != signature:
                self.log.info('Build scripts have changed since last execution!'\
                        'All previous configurations have been cleared!')
                invalid = True
                break
        if invalid:
            self._cache.clear()

    @property
    def tasks(self):
        return self._tasks

    @property
    def cache(self):
        return self._cache

    def run_tasks(self):
        tree = RunnableDependencyTree(self.tasks)
        jobs = Argument('jobs').require_type(int).retrieve(self.env, self.options, default=1)
        executor = TaskExecutionPool(tree, num_jobs=int(jobs))
        res = executor.run()
        return res
