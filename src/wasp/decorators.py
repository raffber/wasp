import functools


class DecoratorStore(object):
    def __init__(self):
        self.init = []
        self.commands = []
        self.generators = []
        self.options = []
        self.create_context = None
        self.handle_options = []


# XXX: this can still be improved a lot
# possibly use transparent object proxies to implement this.
class FunctionDecorator(object):
    def __init__(self, f):
        self._f = f
        functools.update_wrapper(self, f)

    def __call__(self, *args, **kwargs):
        return self._f(*args, **kwargs)


decorators = DecoratorStore()