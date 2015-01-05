import json
from .fs import File
from . import log, factory

CACHE_FILE = 'c4che.json'
"""
name of the cache file.
"""


class Cache(dict):
    """
    Cache dict, which automatically serializes and deserializes itself.
    On the top-level, the cache abstracts groups, which can be accessed using
    :meth:`Cache.prefix`. The objects added must be of type :class:`wasp.util.Serializable` or
    a json-serializable primitive.
    """
    def __init__(self, cachefile):
        """
        Create a cache object.
        :param cachefile: Object of type File which represents the file
            the cache is saved in or loaded from.
        """
        super().__init__()
        assert isinstance(cachefile, File)
        self._cachefile = cachefile

    def prefix(self, prefix):
        """
        Returns a dict which is added of the cache if it does not exist yet.
        Same as :meth:`Cache.__getitem__`.
        """
        if not prefix in self:
            cache = {}
            self[prefix] = cache
            return cache
        return super().__getitem__(prefix)

    def __getitem__(self, prefix):
        """
        Returns a dict which is added of the cache if it does not exist yet.
        Same as :meth:`Cache.__getitem__`.
        """
        # automatically add dict if it's not there yet
        # the reason why we do this, is to allow people reduce the number of
        # code lines by writing things such as:
        # ctx.cache['my-subproject-name']['cc'] = '/usr/bin/gcc'
        # ctx.cache['another-subproject']['cc'] = '/usr/bin/clang'
        # return cc.executable('main.c').use(ctx.cache['my-subproject-name'])
        return self.prefix(prefix)

    def save(self, debug=False):
        """
        Save the content of the cache to the file given in the constructor.
        :param debug: Format the file such that it is human readable.
        """
        # that should not fail, since we ensured the existance
        # of self._cachedir
        jsonified = factory.to_json(self)
        self._cachefile.directory().ensure_exists()
        with open(self._cachefile.path, 'w') as f:
            if debug:
                json.dump(jsonified, f, indent=4, separators=(',', ': '))
            else:
                json.dump(jsonified, f)

    def load(self):
        """
        Loads the cache from the file given in the constructor.
        """
        self.clear()
        try:
            with open(self._cachefile.path, 'r') as f:
                jsonified = None
                try:
                    jsonified = json.load(f)
                except ValueError:
                    pass
            if not isinstance(jsonified, dict):
                # invalid cache file, ignore
                # XXX: cannot use ctx.log
                log.error('Cachefile is invalid. Ignoring.')
            else:
                self.update(factory.from_json(jsonified))
        except FileNotFoundError:
            # nvm, cachefile was probably never written
            # since wasp was never excuted or had anything
            # to write in the first place
            pass