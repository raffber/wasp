

class DecoratorStore(object):
    """
    Class for registring functions using decorators. Decorators may register
    objects in :data:`wasp.decorators`, which is an instance of DecoratorStore().
    If an attribute of this class is accessed and does not exist, it is automatically
    added and initialized with an empty list.
    """
    _other = {}
    metadata = None

    def __setattr__(self, key, value):
        if key in dir(self):
            object.__setattr__(self, key, value)
            return
        if key not in self._other:
            self._other[key] = []
        self._other[key].append(value)

    def __getattr__(self, key):
        if key not in self._other:
            self._other[key] = []
        return self._other[key]
