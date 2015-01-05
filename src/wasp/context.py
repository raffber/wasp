from .options import OptionsCollection
from .cache import Cache, CACHE_FILE
from .signature import SignatureProvider, ProducedSignatures
from .argument import ArgumentCollection
from .environment import Environment
from .fs import Directory, File
from .config import Config
from .generator import GeneratorCollection
from .metadata import Metadata
from .tools import ToolsCollection
from .commands import CommandCollection


class Context(object):
    """
     * signatures: A database of all signatures known to the system.
     * produces_signatures: A database of all signatures which
       have been successfully produced. Comparing current signatures with the
       signatures in this database allows determining if a node (e.g. a file) has
       changed between now and the time when the node was produced (e.g. by a task).
    """

    def __init__(self):
        self._generators = {}
        self._tools = ToolsCollection('wasp-tools')
        self._arguments = ArgumentCollection()
        # initialize options
        self._options = OptionsCollection()
        self._env = Environment()
        self._commands = CommandCollection()
        self._meta = Metadata()
        # create the directories
        self._topdir = Directory('.',  make_absolute=True)
        assert self._topdir.exists, 'The given topdir must exist!!'
        self._cachedir = None
        self._builddir = None
        self._config = Config()
        self._produced_signatures = ProducedSignatures()
        self._signatures = SignatureProvider()
        # create the cache
        self._cache = None

    @property
    def signatures(self):
        return self._signatures

    @property
    def produced_signatures(self):
        return self._produced_signatures

    def get_config(self):
        return self._config

    def set_config(self, config):
        assert isinstance(config, Config)
        self._config = config

    config = property(get_config, set_config)

    def get_meta(self):
        return self._meta

    def set_meta(self, meta):
        self._meta = meta

    meta = property(get_meta, set_meta)

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

    def get_builddir(self):
        return self._builddir

    def set_builddir(self, builddir):
        assert isinstance(builddir, Directory)
        builddir.ensure_exists()
        self._builddir = builddir
        self._cachedir = Directory(self._builddir.join('c4che'))
        self._cache = Cache(File(self._cachedir.join(CACHE_FILE)))

    builddir = property(get_builddir, set_builddir)

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
        self.signatures.save(self._cache)
        d = self.cache.prefix('generators')
        for key, generator_collection in self._generators.items():
            d[key] = generator_collection
        self.cache.save()

    def load(self):
        self._cache.load()
        self.produced_signatures.load(self._cache)
        for key, generator_collection in self._cache.prefix('generators').items():
            self._generators[key] = generator_collection

    @property
    def cache(self):
        return self._cache
