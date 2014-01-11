from .context import Environment
from .options import OptionsCollection


class Argument(object):
    def __init__(self, key, value=None):
        self.key = key
        self.lowerkey = key.lower()
        self.upperkey = key.upper()
        self._value = value

    def get_value(self):
        return self._value

    def set_value(self, value):
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
        if self._value is None:
            self._value = default

