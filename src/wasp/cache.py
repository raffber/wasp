import json
from .fs import Directory
from . import ctx

CACHE_FILE = 'c4che.json'


class Cache(object):
    def __init__(self, cachedir):
        assert isinstance(cachedir, Directory)
        cachedir.ensure_exists()
        self._cachedir = cachedir
        self.d = {}

    def prefix(self, prefix):
        if not prefix in self.d:
            cache = {}
            self.d[prefix] = cache
            return cache
        return self.d[prefix]

    def save(self):
        # that should not fail, since we ensured the existance
        # of self._cachedir
        with open(self._cachedir.join(CACHE_FILE), 'w') as f:
            json.dump(self.d, f)

    def clear(self):
        self.d = {}

    def load(self):
        try:
            with open(self._cachedir.join(CACHE_FILE), 'r') as f:
                try:
                    self.d = json.load(f)
                except ValueError:
                    pass
            if not isinstance(self.d, dict):
                # invalid cache file, ignore
                ctx.log.warning('Cachefile is invalid. Ignoring')
                self.d = {}
        except FileNotFoundError:
            # nvm, cachefile was probably never written
            # since wasp was never excuted or had anything
            # to write in the first place
            pass