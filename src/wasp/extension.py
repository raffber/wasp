from . import log
from .util import load_module_by_name
from . import FatalError

from pkgutil import walk_packages
from importlib import import_module


class ExtensionApi(object):

    def __init__(self, collection):
        self._collection = collection


class ExtensionCollection(dict):

    def __init__(self, search_packages=None):
        super().__init__()
        if search_packages is None:
            search_packages = []
        assert isinstance(search_packages, str) or (isinstance(search_packages, list)
            and all([isinstance(x, str) for x in search_packages])) \
            , 'Argument search_packages: expected str or list thereof.'
        self._search_packages = search_packages if isinstance(search_packages, list) else [search_packages]
        self._meta = {}
        self._api = ExtensionApi(self)

    def register(self, extension=None, meta=None):
        assert extension is not None or meta is not None, 'Either an extension or ' \
                                                          'the metadata to it or both must be given.'
        if extension is None:
            name = meta.name
        else:
            name = extension.name
        if name in self:
            log.warn('Extension `{0}` loaded twice. Ignoring.'.format(name))
            return
        self[name] = extension
        self._meta[name] = meta

    def load_all(self, package_name):
        module = import_module(package_name)
        for (module_finder, name, ispkg) in walk_packages(module.__path__, package_name + '.'):
            self.load(name)

    def load(self, module_name, required=False):
        try:
            load_module_by_name(module_name)
        except ImportError as e:
            if required:
                s = 'Could not load extension {0}: import failed with: {1}'.format(module_name, str(e))
                log.fatal(s)
                raise FatalError(s)

    @property
    def search_packages(self):
        return self._search_packages

    def has(self, name):
        raise NotImplementedError

    @property
    def api(self):
        return self._api


class ExtensionMetadata(object):
    name = 'my-extension'
    description = 'Unknown Extension'
    author = 'anonymous'
    website = None
    documentation = None


class ExtensionBase(object):

    def config_loaded(self, config):
        return NotImplemented

    def context_created(self):
        return NotImplemented

    def find_scripts(self):
        return NotImplemented

    def before_load_scripts(self):
        return NotImplemented

    def top_script_loaded(self, module):
        return NotImplemented

    def all_scripts_loaded(self):
        return NotImplemented

    def initialized(self):
        return NotImplemented

    def retrieve_options(self, options):
        return NotImplemented

    def options_parsed(self, options):
        return NotImplemented

    def run_command(self, name):
        return NotImplemented

    def run_task(self, task_container):
        return NotImplemented

    def run_task_collection(self, tasks):
        return NotImplemented

    def create_executor(self, command_name):
        return NotImplemented

    def tasks_collected(self, tasks):
        return NotImplemented

    def tasks_execution_started(self, tasks, executor, dag):
        return NotImplemented

    def tasks_execution_finished(self, tasks, executor, dag):
        return NotImplemented

    def task_started(self, task, executor, dag):
        return NotImplemented

    def task_finished(self, task, executor, dag):
        return NotImplemented

    def command_started(self, name):
        return NotImplemented

    def command_finished(self, name, success=False):
        return NotImplemented

    def command_failed(self, name):
        return NotImplemented

    def command_success(self, name):
        return NotImplemented

    @property
    def name(self):
        raise NotImplementedError
