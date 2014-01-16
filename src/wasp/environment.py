import os


class Environment(object):
    def __init__(self, cache):
        self._cache = cache
        self._env = []
        self.load_from_cache()

    def __getitem__(self, key):
        return self._env[key]

    def __setitem__(self, key, value):
        self._env[key] = value

    def __hasitem__(self, key):
        if key in self._env:
            return True
        return False

    def get(self, key, *args):
        if key in self._env:
            return self._env[key]
        if len(args) == 0:
            return None
        return args[0]

    def load_from_cache(self):
        # copy, such that we don't change the cache
        self._env = dict(self._cache.getcache('env'))

    def load_from_env(self):
        self._env = dict(os.environ)

    def save(self):
        self._cache.setcache('env', self._env)