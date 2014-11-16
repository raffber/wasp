from .task_collection import TaskCollection
from .options import OptionsCollection
from .cache import Cache
from .signature import SignatureProvider, FileSignature, SignatureStore
from .arguments import Argument
from .ui import Log
from .environment import Environment
from .result import TaskResultCollection
from .util import load_module_by_path, Serializable
from .tools import ToolError, NoSuchToolError
from .tools import proxies
from .fs import TOP_DIR, Directory
from .store import Store
from .defer import DeferredTaskCollection
import os


class Context(object):

    def __init__(self, projectname='myproject', recurse_files=[], builddir='build', prefix='/usr'):
        # we need to get the initialization order right.
        # the simplest way to do this is to initialize things first
        # that have no dependencies
        self._log = Log()
        self._results = TaskResultCollection()
        self.projectname = projectname
        # create the directories
        self._topdir = Directory(TOP_DIR,  make_absolute=True)
        assert self._topdir.valid, 'The given topdir must exist!!'
        self._builddir = Directory(builddir)
        self._builddir.ensure_exists()
        self._cachedir = Directory(self._builddir.join('c4che'))
        self._prefix = Directory(os.environ.get('PREFIX', prefix))
        # create the signature for this build script
        # the current build script
        fname = self._topdir.join('build.py')
        self._scripts_signatures = {fname: FileSignature(fname)}
        for fpath in recurse_files:
            self._scripts_signatures[fpath] = FileSignature(fpath)
        # create the cache
        self._cache = Cache(self._cachedir)
        self._deferred = DeferredTaskCollection()
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
        self._tasks = TaskCollection()
        self._tooldir = Directory('wasp-tools')
        self._results.load(self._cache.getcache('results'))
        self._tools = {}
        self._arguments = {}

    def get_tooldir(self):
        return self._tooldir

    def set_tooldir(self, tooldir):
        if isinstance(tooldir, str):
            tooldir = Directory(tooldir)
        assert isinstance(tooldir, Directory), 'tooldir must either be a path to a directory or a WaspDirectory'
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
    def arguments(self):
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
        self._deferred.save(self.cache)
        self.cache.save()

    def load(self):
        self._cache.load()
        self._deferred.load(self.cache)
        signatures = self._cache.getcache('script-signatures')
        invalid = False
        for (fpath, signature) in self._scripts_signatures.items():
            ser_sig = signatures.get(fpath, None)
            if ser_sig is None:
                invalid = True
                # continue to see if the files have actually changed
                continue
            old_sig = FileSignature.from_json(ser_sig)
            if old_sig != signature:
                self.log.info('Build scripts have changed since last execution!' \
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

    def deferred(self, commandname):
        if commandname not in self._deferred:
            self._deferred[commandname] = TaskCollection(traits=[Serializable])
        return self._deferred[commandname]

    def run_tasks(self):
        #tree = RunnableDependencyTree(self.tasks)
        jobs = Argument('jobs').require_type(int).retrieve(self.env, self.options, default=1)
        #executor = TaskExecutionPool(tree, num_jobs=int(jobs))
        #res = executor.run()
        return None