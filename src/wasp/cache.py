import json
from .fs import Directory
from . import log, factory

CACHE_FILE = 'c4che.json'


class Cache(dict):
    def __init__(self, cachedir):
        assert isinstance(cachedir, Directory)
        cachedir.ensure_exists()
        self._cachedir = cachedir


    def prefix(self, prefix):
        if not prefix in self:
            cache = {}
            self[prefix] = cache
            return cache
        return super().__getitem__(prefix)

    def __getitem__(self, prefix):
        # automatically add dict if it's not there yet
        # the reason why we do this, is to allow people reduce the number of
        # code lines by writing things such as:
        # ctx.cache['my-subproject-name']['cc'] = '/usr/bin/gcc'
        # ctx.cache['another-subproject']['cc'] = '/usr/bin/clang'
        # return cc.executable('main.c').use(ctx.cache['my-subproject-name'])
        return self.prefix(prefix)

    def save(self):
        # that should not fail, since we ensured the existance
        # of self._cachedir
        jsonified = factory.to_json(self)
        with open(self._cachedir.join(CACHE_FILE), 'w') as f:
            json.dump(jsonified, f, indent=4, separators=(',', ': '))
            #json.dump(jsonified, f)

    def load(self):
        self.clear()
        try:
            with open(self._cachedir.join(CACHE_FILE), 'r') as f:
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