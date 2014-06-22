from .decorators import decorators
from . import ctx


class CommandFailedError(Exception):
    pass


class Command(object):
    def __init__(self, name, fun, description=None):
        self._depends = []
        self._name = name
        self._fun = fun
        self._description = description or name

    @property
    def depends(self):
        return self._depends

    @property
    def name(self):
        return self._name

    def fail(self, msg):
        ctx.log.fatal(msg)
        raise CommandFailedError(msg)

    def run(self):
        fail = False
        msg = ''
        command_cache = ctx.cache.getcache('commands')
        for dep in self._depends:
            com_info = command_cache.get(dep)
            if com_info is not None:
                if not com_info.get('success', False):
                    fail = True
                    msg = '{0} failed!'.format(dep)
                    break
            else:
                msg = '{0} never run!'.format(dep)
                fail = True
                break
        if fail:
            self.fail('Command dependency not fullfilled: {0}'.format(msg))
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


class build(object):
    def __init__(self, f):
        decorators.commands.append(BuildCommand(f))


class install(object):
    def __init__(self, f):
        decorators.append(InstallCommand(f))


class configure(object):
    def __init__(self, f):
        decorators.commands.append(ConfigureCommand(f))


class clean(object):
    def __init__(self, f):
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