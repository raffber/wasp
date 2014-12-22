from .decorators import decorators
from .util import ArgumentFunctionDecorator


class CommandFailedError(Exception):
    pass


class Command(object):
    def __init__(self, name, fun, description=None, depends=None, produce=None):
        self._depends = [] if depends is None else depends
        if isinstance(self._depends, str):
            self._depends = [self._depends]
        assert isinstance(self._depends, list), 'Expected string or list thereof.'
        self._name = name
        self._fun = fun
        self._description = description or name
        self._produce = produce

    @property
    def depends(self):
        return self._depends

    @property
    def name(self):
        return self._name

    def run(self):
        return self._fun()

    @property
    def description(self):
        return self._description

    @property
    def produce(self):
        return self._produce


class command(ArgumentFunctionDecorator):
    def __init__(self, name, depends=None, description=None, produce=None):
        self._name = name
        self._depends = depends
        self._description = description
        self._produce = produce

    def __call__(self, f):
        if self._produce is not None:
            produce = self._produce
        else:
            produce = ':def-' + f.__name__
        decorators.commands.append(Command(self._name, f,
                                           description=self._description, depends=self._depends,
                                           produce=produce))
        return super().__call__(f)