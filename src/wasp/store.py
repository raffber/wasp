
class Store(dict):
    def __init__(self, cache):
        self._cache = cache

    def __setitem__(self, key, value):
        self._cache.set('store', key, value)

    def __getitem__(self, key):
        ret = self._cache.get('store', key)
        if ret is None:
            raise KeyError
        return ret

    def get(self, key, *args):
        if len(args) > 1:
            raise TypeError('Only one argument may be provided as default argument if "key" does not exits')
        ret = self._cache.get('store', key)
        if ret is not None:
            return ret
        if len(args) == 0:
            return None
        return args[1]