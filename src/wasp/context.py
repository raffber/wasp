from .options import OptionsCollection
from .cache import Cache
from .signature import FileSignature
from .argument import ArgumentCollection
from .environment import Environment
from .util import load_module_by_path
from .tools import ToolError, NoSuchToolError
from .tools import proxies
from .fs import Directory
from .config import Config
from .generator import GeneratorCollection
from .metadata import Metadata
from . import produced_signatures, signatures, log
from .commands import CommandCollection

import os


class Context(object):

    def __init__(self, meta=None, config=None, recurse_files=[], builddir='build'):
        self._generators = {}
        self._tools = {}
        self._arguments = ArgumentCollection()
        # initialize options
        self._options = OptionsCollection()
        self._env = Environment()
        self._commands = CommandCollection()
        self._tooldir = Directory('wasp-tools')
        # we need to get the initialization order right.
        # the simplest way to do this is to initialize things first
        # that have no dependencies
        if meta is None:
            meta = Metadata()
        self._meta = meta
        # create the directories
        self._topdir = Directory('.',  make_absolute=True)
        assert self._topdir.exists, 'The given topdir must exist!!'
        self._builddir = Directory(builddir)
        self._builddir.ensure_exists()
        self._cachedir = Directory(self._builddir.join('c4che'))
        if config is None:
            self._config = Config()
        else:
            self._config = config
        # create the signature for this build script
        # the current build script
        fname = self._topdir.join('build.py')
        self._scripts_signatures = {fname: FileSignature(fname)}
        for fpath in recurse_files:
            self._scripts_signatures[fpath] = FileSignature(fpath)
        # create the cache
        self._cache = Cache(self._cachedir)

    def get_tooldir(self):
        return self._tooldir

    def set_tooldir(self, tooldir):
        if isinstance(tooldir, str):
            tooldir = Directory(tooldir)
        assert isinstance(tooldir, Directory), 'tooldir must either be a path to a directory or a WaspDirectory'
        tooldir.ensure_exists()
        self._tooldir = tooldir

    tooldir = property(get_tooldir, set_tooldir)

    @property
    def config(self):
        return self._config

    @property
    def meta(self):
        return self._meta

    def load_tool(self, toolname, *args, path=None):
        if toolname in self._tools:
            ret = self._tools[toolname]
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
                    # TODO: why is it bugging any other way?!
                    # specifically, proxy.__assign_object(asdf) does not
                    # seem to work. The attriute name gets strangely converted
                    # into _Context__assign_object... even if calling __getattribute__
                    # directly
                    p = proxies[toolname]
                    data = object.__getattribute__(p, '_data')
                    data['obj'] = module
                ret = module
            except FileNotFoundError:
                raise NoSuchToolError('Tool with name `{0}` not found in `{1}`'.format(toolname, path))
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

    def generators(self, commandname):
        if commandname not in self._generators:
            self._generators[commandname] = GeneratorCollection()
        return self._generators[commandname]

    @property
    def topdir(self):
        return self._topdir

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
    def commands(self):
        return self._commands

    def save(self):
        d = self.cache.prefix('script-signatures')
        for fpath, signature in self._scripts_signatures.items():
            d[fpath] = signature
        signatures.save(self._cache)
        d = self.cache.prefix('generators')
        for key, generator_collection in self._generators.items():
            d[key] = generator_collection
        self.cache.save()

    def load(self):
        self._cache.load()
        produced_signatures.load(self._cache)
        for key, generator_collection in self._cache.prefix('generators').items():
            self._generators[key] = generator_collection
        signatures = self._cache.prefix('script-signatures')
        invalid = False
        for (fpath, signature) in self._scripts_signatures.items():
            if fpath not in signatures:
                continue
            old_sig = signatures[fpath]
            if old_sig != signature:
                log.info('Build scripts have changed since last execution!'
                              'All previous configurations have been cleared!')
                invalid = True
                break
        if invalid:
            self._cache.clear()

    @property
    def cache(self):
        return self._cache
