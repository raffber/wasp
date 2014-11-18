from .environment import Environment
from .options import OptionsCollection
from . import ctx, factory
from .util import Serializable


class MissingArgumentError(Exception):
    pass


class ArgumentCollection(dict, Serializable):

    def add(self, arg):
        assert isinstance(arg, Argument), 'Can only add Argument to ArgumentCollection'
        self[arg.key] = arg

    def to_json(self):
        d = super().to_json()
        d['arguments'] = [arg.to_json() for arg in self.items()]
        return d

    @classmethod
    def from_json(cls, d):
        self = cls()
        for argjson in d['arguments']:
            arg = Argument.from_json(argjson)
            self.add(arg)
        return self


class Argument(Serializable):

    def __init__(self, key, value=None, type=str):
        self.key = key
        self._type = type
        self.lowerkey = key.lower()
        self.upperkey = key.upper()
        self._value = None
        self._required_type = None
        self._use_type(type)
        self._set_value(value)

    def to_json(self):
        d = super().to_json()
        d['value'] = factory.to_json(self._value)
        d['key'] = self.key
        return d

    @classmethod
    def from_json(cls, d):
        value = factory.from_json(d['value'])
        key = d['key']
        return cls(key, value=value, type=type(value))

    def get_value(self):
        return self._value

    def _use_type(self, tp):
        assert issubclass(tp, Serializable) or tp == str or \
            tp == int or tp == float or tp == list or tp == dict
        self._required_type = tp
        self._check_convert_value(self.value)

    def set_value(self, value):
        """
        Raises: ValueError if type conversion from value to the required type is not successful.
        """
        if self._required_type is not None and value is not None:
            assert isinstance(value, self._required_type),\
                'Argument {0} must be of type {1}!'.format(self.lowerkey, str(self._required_type))
        self._value = (self._required_type)(value)

    value = property(get_value, set_value)

    def _retrieve_from_single(self, arg):
        if isinstance(arg, Environment):
            # environment variable
            return arg.get(self.upperkey)
        elif isinstance(arg, OptionsCollection):
            return arg.get(self.lowerkey, None)
        elif isinstance(arg, Environment):
            # environment variable
            return arg.get(self.upperkey)
        elif isinstance(arg, dict):
            # keyword argument
            return arg.get(self.lowerkey, None)
        elif isinstance(arg, str):
            return arg
        elif isinstance(arg, list):
            return arg
        return None

    def retrieve(self, *args, default=None):
        for a in args:
            ret = self._retrieve_from_single(a)
            if ret is not None:
                self.value = ret
                break
        if self.value is None:
            self.value = default
        return self.value

    def retrieve_all(self):
        self.retrieve(ctx.arguments, ctx.options, ctx.configure_options, ctx.env)
        return self.value

    def require_type(self, tp):
        self._required_type = tp
        self._use_type(self._value)
        return self

    @property
    def is_empty(self):
        return self.value is None

    def assign(self, value):
        self.value = value
        return self
