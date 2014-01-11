from .decorators import decorators


class Command(object):
    def __init__(self, name, fun):
        self._depends = []
        self._name = name
        self._fun = fun

    @property
    def depends(self):
        return self._depends

    def name(self):
        return self._name

    def run(self):
        # TODO: check for dependencies
        self._fun()


class ConfigureCommand(Command):
    def __init__(self, fun):
        super().__init__('configure', fun)


class BuildCommand(Command):
    def __init__(self, fun):
        super().__init__('build', fun)
        self.depends.append('configure')


class InstallCommand(Command):
    def __init__(self, fun):
        super().__init__('install', fun)
        self.depends.append('build')


class build(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.commands.append(('build', f, []))
        return f


class install(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.append(('install', f, []))
        return f


class configure(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.commands.append(('configure', f, []))
        return f


class command(object):
    def __init__(self, name, depends=[]):
        self._name = name
        if isinstance(depends, str):
            depends = [depends]
        self._depends = depends

    def __call__(self, f):
        decorators.commands.append(self._name, f, self._depends)
        return f