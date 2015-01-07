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
from .util import Namespace


class Context(object):
    """
    This object captures the state of the application. It is accessible using
    :data:`wasp.ctx`. This class only contains minor functionality components
    and only acts as a locator for data.
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
        self._g = Namespace()

    @property
    def g(self):
        """
        Returns a :class:`wasp.util.Namespace` object, which allows
        setting arbitrary attributes. This is useful for communicating
        data between different build modules.
        """
        return self._g

    @property
    def signatures(self):
        """
        A database of all signatures known to the system.
        """
        return self._signatures

    @property
    def produced_signatures(self):
        """
        A database of all signatures which have been successfully produced.
        Comparing current signatures with the signatures in this database
        allows determining if a node (e.g. a file) has changed between now
        and the time when the node was produced (e.g. by a task).
        """
        return self._produced_signatures

    def get_config(self):
        return self._config

    def set_config(self, config):
        assert isinstance(config, Config)
        self._config = config

    config = property(get_config, set_config)
    """
    Returns the configuration of the project.
    """

    def get_meta(self):
        return self._meta

    def set_meta(self, meta):
        self._meta = meta

    meta = property(get_meta, set_meta)
    """
    Returns the metadata of the project.
    """

    @property
    def tools(self):
        """
        Returns an object of type :class:`wasp.tools.ToolCollection` which
        contains the currently loaded tools and provides a facililty
        to load more tools.
        """
        return self._tools

    def generators(self, commandname):
        if commandname not in self._generators:
            self._generators[commandname] = GeneratorCollection()
        return self._generators[commandname]

    @property
    def topdir(self):
        """
        Returns the top directory of the project.
        """
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
    """
    Allows adjusting the build directory of the project.
    By default, task producing files should make sure that
    they write to this directory and leave the topdir clean.
    Furthermore, the cache directory can be found in <builddir>/c4che/
    """

    @property
    def cachedir(self):
        """
        Returns the cache directory.
        """
        return self._cachedir

    @property
    def env(self):
        """
        Returns the environment the application runs in.
        :return: Object of type :class:`wasp.environmnet.Environment`
        """
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
