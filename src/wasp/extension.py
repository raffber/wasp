from . import log
from .util import load_module_by_name
from . import FatalError

from pkgutil import walk_packages
from importlib import import_module


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


class ExtensionMetadata(object):
    name = ''
    description = 'Unknown Extension'
    author = 'anonymous'
    website = None
    documentation = None

    @classmethod
    def from_json(cls, d):
        assert isinstance(d, dict), 'Invalid json for extension metadata. Expected dict.'
        assert 'name' in d, 'Extension metadata must contain the extension name.'
        self = cls()
        self.description = d.get('description', self.description)
        self.author = d.get('author', self.author)
        self.website = d.get('website', self.website)
        self.documentation = d.get('documentation', self.documentation)
        self.name = d.get('name', self.name)
        return self


class ExtensionBase(object):

    def init(self):
        pass

    def monkeypatch(self):
        pass

    def context_loaded(self, context):
        pass

    def task_started(self, task):
        pass

    def task_finished(self, task):
        pass

    @property
    def name(self):
        raise NotImplementedError
