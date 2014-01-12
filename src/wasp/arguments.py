from .context import Environment
from .options import OptionsCollection


class Argument(object):
    def __init__(self, key, value=None):
        self.key = key
        self.lowerkey = key.lower()
        self.upperkey = key.upper()
        self._value = value
        self._required_type = None

    def get_value(self):
        return self._value

    def _check_type(self, value):
        if self._required_type is not None and self._value is not None:
            assert(isinstance(value, self._required_type)
                   , 'Argument {0} must be of type {1}!'.format(self.lowerkey, str(self._required_type))).

    def set_value(self, value):
        self._check_type(value)
        self._value = value

    value = property(get_value, set_value)

    def _retrieve_from_single(self, arg):
        if isinstance(arg, Environment):
            # environment variable
            return arg.get(self.upperkey)
        elif isinstance(arg, dict):
            # keyword argument
            return arg.get(self.lowerkey, None)
        elif isinstance(arg, OptionsCollection):
            return arg.get(self.lowerkey, None)
        elif isinstance(arg, str):
            return arg
        elif isinstance(arg, list):
            return arg
        return None

    def retrieve(self, *args, default=''):
        for a in args:
            ret = self._retrieve_from_single(a)
            if ret is not None:
                self.value = ret
                break
        if self.value is None:
            self.value = default
        return self.value

    def require_type(self, tp):
        self._required_type = tp
        self._check_type(self._value)
        return self
