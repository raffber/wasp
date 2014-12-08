from .decorators import decorators, FunctionDecorator


class CommandFailedError(Exception):
    pass


class Trigger(object):
    def check(self):
        raise NotImplementedError


class Command(object):
    def __init__(self, name, fun, description=None):
        self._depends = []
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


class ConfigureCommand(Command):
    def __init__(self, fun):
        super().__init__('configure', fun, description='Configures the project')


class BuildCommand(Command):
    def __init__(self, fun):
        super().__init__('build', fun, description='Builds the project')
        self.depends.append('configure')


class InstallCommand(Command):
    def __init__(self, fun):
        super().__init__('install', fun, description='Installs the project')
        self.depends.append('build')


class CleanCommand(Command):
    def __init__(self, fun):
        super().__init__('clean', fun, description='Clean generated files.')


class build(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(BuildCommand(f))


class install(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.append(InstallCommand(f))


class configure(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(ConfigureCommand(f))


class clean(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(CleanCommand(f))


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