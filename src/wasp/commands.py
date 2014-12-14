from .decorators import decorators
from .util import FunctionDecorator


class CommandFailedError(Exception):
    pass


class Command(object):
    def __init__(self, name, fun, description=None, depends=None):
        self._depends = [] if depends is None else depends
        if isinstance(self._depends, str):
            self._depends = [self._depends]
        assert isinstance(self._depends, list), 'Expecte string or list thereof.'
        self._name = name
        self._fun = fun
        self._description = description or name
        self._triggers = []

    @property
    def triggers(self):
        return self._triggers

    def check_triggers(self):
        for trigger in self._triggers:
            if trigger.check():
                return True
        return False

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


class command(object):
    def __init__(self, name, depends=[], description=None):
        self._name = name
        if isinstance(depends, str):
            depends = [depends]
        assert isinstance(depends, list), 'command dependencies must be given as string or list thereof'
        self._depends = depends
        self._description = description

    def __call__(self, f):
        com = Command(self._name, f, description=self._description)
        for dep in self._depends:
            com.depends.append(dep)
        decorators.commands.append(com)
        return f