import json
from .directory import WaspDirectory
from .ui import log


CACHE_FILE = 'c4che.json'


class Cache(object):
    def __init__(self, cachedir):
        assert(isinstance(cachedir, WaspDirectory))
        cachedir.ensure_exits()
        self._cachedir = cachedir
        self.d = {}

    def set(self, cachename, key, value):
        if cachename not in self.d:
            cache = {}
            self.d[cachename] = cache
        else:
            cache = self.d[cachename]
        if not isinstance(cache, dict):
            log.warning('Cachefile is invalid. Ignoring')
            cache = {}
            self.d[cachename] = cache
        cache[key] = value

    def get(self, cachename, key, *args):
        if len(args) > 1:
            raise TypeError('At most one additional argument is allowed.')
        default = args[0] if len(args) == 1 else None
        cache = self.d.get(cachename, None)
        if cache is not None:
            return cache.get(key, default)
        return None

    def getcache(self, cachename):
        if not cachename in self.d:
            cache = {}
            self.d[cachename] = cache
            return cache
        return self.d[cachename]

    def setcache(self, cachename, cache):
        self.d[cachename] = cache

    def flush(self):
        # that should not fail, since we ensured the existance
        # of self._cachedir
        with open(self._cachedir.join(CACHE_FILE), 'w') as f:
            json.dump(f)

    def load(self):
        try:
            with open(self._cachedir.join(CACHE_FILE), 'r') as f:
                self.d = json.load(f)
            if not isinstance(self.d, dict):
                # invalid cache file, ignore
                log.warning('Cachefile is invalid. Ignoring')
                self.d = {}
        except FileNotFoundError:
            # nvm, cachefile was probably never written
            # since wasp was never excuted or had anything
            # to write in the first place
            pass