from .options import OptionsCollection
from .cache import Cache
from .signature import FileSignature
from .argument import ArgumentCollection
from .environment import Environment
from .fs import Directory
from .config import Config
from .generator import GeneratorCollection
from .metadata import Metadata
from .tools import ToolsCollection
from . import produced_signatures, signatures, log
from .commands import CommandCollection


class Context(object):

    def __init__(self, meta=None, config=None, recurse_files=[], builddir='build'):
        self._generators = {}
        self._tools = ToolsCollection('wasp-tools')
        self._arguments = ArgumentCollection()
        # initialize options
        self._options = OptionsCollection()
        self._env = Environment()
        self._commands = CommandCollection()
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

    @property
    def config(self):
        return self._config

    @property
    def meta(self):
        return self._meta

    @property
    def tools(self):
        return self._tools

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
                log.info(log.format_info('Build scripts have changed since last execution!',
                          'All previous configurations have been cleared!'))
                self._cache.clear()

    @property
    def cache(self):
        return self._cache
