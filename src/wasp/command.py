from .decorators import decorators


class CommandFailedError(Exception):
    pass


class Command(object):
    def __init__(self, name, fun, depends=[], description=None):
        self._depends = depends
        self._name = name
        self._fun = fun
        self._description = description or name

    @property
    def depends(self):
        return self._depends

    def name(self):
        return self._name

    def run(self):
        # TODO: check for dependencies
        self._fun()

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
        super().__init__('install', fun, description='Install the project')
        self.depends.append('build')


class build(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.commands.append(BuildCommand(f))
        return f


class install(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.append(InstallCommand(f))
        return f


class configure(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.commands.append(ConfigureCommand(f))
        return f


class command(object):
    def __init__(self, name, depends=[], description=None):
        self._name = name
        if isinstance(depends, str):
            depends = [depends]
        self._depends = depends
        self._description = description

    def __call__(self, f):
        com = Command(self._name, f, depends=self._depends, description=self._description)
        decorators.commands.append(com)
        return f