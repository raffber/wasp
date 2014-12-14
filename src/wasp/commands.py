from .decorators import decorators
from .util import FunctionDecorator


class CommandFailedError(Exception):
    pass


class Command(object):
    def __init__(self, name, fun, description=None, depends=None):
        self._depends = [] if depends is None else depends
        if isinstance(self._depends, str):
            self._depends = [self._depends]
        assert isinstance(self._depends, list), 'Expected string or list thereof.'
        self._name = name
        self._fun = fun
        self._description = description or name

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


class command(FunctionDecorator):
    def __init__(self, f, name, depends=None, description=None):
        super().__init__(f)
        decorators.commands.append(Command(name, f, description=description, depends=depends))
