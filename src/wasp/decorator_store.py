

class DecoratorStore(object):
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
