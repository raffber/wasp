import os
import json
from .util import load_module_by_path
from . import log


class ExtensionCollection(dict):

    def __init__(self, search_path=None):
        if search_path is None:
            search_path = []
        assert isinstance(search_path, str) or (isinstance(search_path, list)
            and all([isinstance(x, str) for x in search_path])), 'Argument search_path: expected str or list thereof.'
        self._search_path = search_path if isinstance(search_path, list) else [search_path]
        self._extension = {}
        self._meta = {}
        self._recently_added = []

    def register(self, extension=None, meta=None):
        assert extension is not None or meta is not None, 'Either an extension or ' \
                                                          'the metadata to it or both must be given.'
        if extension is None:
            name = meta.name
        else:
            name = extension.name
        if name in self._extension:
            log.warn('Extension `{0}` loaded twice. Ignoring.'.format(name))
            return
        self._recently_added.append(name)
        self._extension[name] = extension
        self._meta[name] = meta

    def load_from_directory(self, fpath, loading=None):
        if '__pycache__' in fpath:
            return
        meta = os.path.join(fpath, 'meta.json')
        if os.path.exists(meta):
            with open(meta, 'r') as f:
                d = json.load(f)
            meta = ExtensionMetadata.from_json(d)
            selfname = meta.name
            if selfname in loading:
                raise ValueError('Circular dependency among extensions.')
            loading_new = list(loading)
            loading_new.append(selfname)
            for extension in meta.requires:
                if extension in self._extension:
                    continue
                self.load_in_search_path(name=extension, loading=loading_new)
        import_path = os.path.join(fpath, '__init__.py')
        if not os.path.exists(import_path):
            log.warn('Extension directory `{0}` exists but does not contain an __init__.py file. Skipping.'.format(import_path))
            return
        self._import(import_path, meta=meta)

    def load_in_search_path(self, name=None, loading=None):
        for sp in self.search_path:
            if name is not None:
                dirpath = os.path.join(sp, name)
                fpath = os.path.join(sp, name, '.py')
                if os.path.isdir(dirpath):
                    self.load_from_directory(dirpath, loading=loading)
                elif os.path.isfile(fpath):
                    self.load_from_file(fpath, loading=loading)
            else:
                for fpath in os.listdir(sp):
                    fpath = os.path.join(sp, fpath)
                    if os.path.isdir(fpath):
                        self.load_from_directory(fpath, loading=loading)
                    elif os.path.isfile(fpath):
                        self.load_from_file(fpath, loading=loading)

    @property
    def search_path(self):
        return self._search_path

    def load_from_file(self, fpath,  loading=None):
        self._import(fpath, meta=None)

    def _import(self, fpath, meta=None):
        self._recently_added = []
        load_module_by_path(fpath)
        for key in self._recently_added:
            if self._meta[key] is not None:
                self._meta = meta
        self._recently_added = []


class ExtensionMetadata(object):
    wants = []
    requires = []
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
        self.wants = cls._parse_extension_name_list(d.get('wants'))
        self.requires = cls._parse_extension_name_list(d.get('requires'))
        self.description = d.get('description', self.description)
        self.author = d.get('author', self.author)
        self.website = d.get('website', self.website)
        self.documentation = d.get('documentation', self.documentation)
        self.name = d.get('name', self.name)
        return self

    @classmethod
    def _parse_extension_name_list(cls, lst):
        if lst is None:
            return []
        assert isinstance(lst, list) or isinstance(lst, str), 'Invalid json for extension' \
                                                              ' metadata. Expected str or list.'
        if isinstance(lst, list):
            assert all([isinstance(x, str) for x in lst])
            return lst
        return [lst]


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
