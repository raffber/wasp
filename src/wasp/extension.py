import os
import json
from .util import load_module_by_path
from . import ctx


class ExtensionCollection(dict):

    def __init__(self, search_path):
        assert isinstance(search_path, str) or (isinstance(search_path, list)
            and all([isinstance(x, str) for x in search_path])), 'Argument search_path: expected str or list thereof.'
        self._search_path = search_path if isinstance(search_path, list) else [search_path]
        self._extension = {}
        self._meta = {}
        self._recently_added = []

    def register(self, extension, meta=None):
        self._recently_added.append(extension.name)
        self._extension[extension.name] = extension
        self._meta[extension.name] = meta

    def load_from_directory(self, fpath, loading=None):
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
                self.load_in_search_path(extension, loading=loading_new)
        import_path = os.path.join(fpath, '__init__.py')
        if not os.path.exists(import_path):
            ctx.log.warn('Extension directory `{0}` exists but does not contain an __init__.py file. Skipping.')
            return
        self._import(import_path, meta=meta)

    def load_in_search_path(self, extension, loading=None):
        pass

    def load_from_file(self, fpath,  loading=None):
        pass

    def _import(self, fpath, meta=None):
        self._recently_added = []
        load_module_by_path(fpath)
        for key in self._recently_added:
            if self._meta[key] is not None:
                self._meta = meta
        self._recently_added = []

    def _parse_meta(self, d):
        pass


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


def has_ext(typ, *extensions):
    if all([x in ctx.ext for x in extensions]):
        return typ
    return type(None)