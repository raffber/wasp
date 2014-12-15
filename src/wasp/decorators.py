

class DecoratorStore(object):
    _other = {}
    create_context = None
    metadata = None

    def __setattr__(self, key, value):
        if key not in self._other:
            self._other[key] = []
        self._other[key].append(value)

    def __getattr__(self, key):
        if key not in self._other:
            self._other[key] = []
        return self._other[key]

decorators = DecoratorStore()