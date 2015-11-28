from .util import FunctionDecorator, Serializable
from . import decorators


class Metadata(Serializable):
    """
    Storage class for project metadata. It allows
    setting arbitrary string key-value pairs which can
    then be accessed using ``ctx.meta``. This information
    may be used by external tools for example to create an
    installable package.

    Metadata can be set either within a build script or using a
    wasprc.json file.

    Note: This class always contains the following keys (with at least
    a sensible default value)::

        * projectname (defaults to 'myproject')
        * projectid (to be used as name in the filesystem. defaults to 'myproject')
    """
    projectname = 'myproject'
    projectid = None
    _other = {}

    def __init__(self):
        if self.projectid is None:
            self.projectid = self.projectname
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

    def as_dict(self):
        ret = dict(self._other)
        ret.update({
            'projectname': self.projectname,
            'projectid': self.projectid
        })
        return ret

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
    """
    Decorator for annotating a function, which is called by
    ``wasp``. This function should return a :class:`Metadata`
    object to be stored in ``ctx.meta``.
    """
    def __init__(self, f):
        super().__init__(f)
        decorators.metadata = f