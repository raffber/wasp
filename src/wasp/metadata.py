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
        assert value is None or isinstance(value, str) or all([isinstance(x, str) for x in value])
        self._other[key] = value

    def __getattr__(self, item):
        if item in self._other:
            return self._other[item]
        return None

    @classmethod
    def from_json(cls, d):
        self = cls()
        assert isinstance(d, dict), 'Expected a dict as serialization'
        for k, v in d.items():
            self.__setattribute__(k, v)

    def to_json(self):
        ret = super().to_json()
        for k in dir(self):
            if k.startswith('__') or k == 'to_json':
                continue
            ret[k] = self.__getattribute__(k)
        for k, v in self._other.items():
            ret[k] = v
        return ret


class metadata(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.metadata = f