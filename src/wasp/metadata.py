from .util import FunctionDecorator, Serializable
from .decorators import decorators


class Metadata(Serializable):
    projectname = None
    _other = {}
    projectid = 'myproject'

    def __init__(self):
        if self.projectname is None:
            self.projectname = self.projectid
        self._other = {}

    def __setattr__(self, key, value):
        self.set(key, value)

    def __getattr__(self, item):
        return self.get(item)

    def get(self, key):
        if key in dir(self):
            return object.__getattribute__(self, key)
        if key in self._other:
            return self._other[key]
        return None

    def set(self, key, value):
        assert value is None or isinstance(value, str) or all([isinstance(x, str) for x in value])
        if key not in dir(self):
            self._other[key] = value
        object.__setattr__(self, key, value)

    @classmethod
    def from_json(cls, d):
        self = cls()
        assert isinstance(d, dict), 'Expected a dict as serialization'
        for k, v in d.items():
            self.set(k, v)
        return self

    def to_json(self):
        ret = super().to_json()
        for k in dir(self):
            if k.startswith('__') or k == 'to_json':
                continue
            ret[k] = self.get(k)
        for k, v in self._other.items():
            ret[k] = v
        return ret


class metadata(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.metadata = f