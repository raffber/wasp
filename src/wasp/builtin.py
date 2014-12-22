from . import options, signatures, ctx, init
from .decorators import decorators
from .main import run_command
from .util import FunctionDecorator
from .commands import Command, command
from .options import FlagOption, handle_options
from .argument import Argument
from .fs import remove


@handle_options
def _init_default_args(options):
    arg = Argument('prefix').retrieve_all()
    if arg.is_empty:
        ctx.arguments.add(arg.assign('/usr'))


@options
def _add_builtin_options(option_collection):
    builtin_group = option_collection.group('builtin')
    builtin_group.description = 'Builtin options for wasp'
    builtin_group.add(FlagOption('q', 'Set verbosity level to 0 [QUIET]', prefix='-'))
    builtin_group.add(FlagOption('v', 'Set verbosity level to 1 [FATAL]', prefix='-'))
    builtin_group.add(FlagOption('vv', 'Set verbosity level to 2 [ERROR]', prefix='-'))
    builtin_group.add(FlagOption('vvv', 'Set verbosity level to 3 [WARN] <- default', default=True, prefix='-'))
    builtin_group.add(FlagOption('vvvv', 'Set verbosity level to 4 [INFO]', prefix='-'))
    builtin_group.add(FlagOption('vvvvv', 'Set verbosity level to 5 [DEBUG]', prefix='-'))


@handle_options
def _handle_builtin_options(option_handler):
    verbosity_one = Argument('v', type=bool).retrieve(ctx.options).value
    verbosity_two = Argument('vv', type=bool).retrieve(ctx.options).value
    verbosity_three = Argument('vvv', type=bool).retrieve(ctx.options).value
    verbosity_four = Argument('vvvv', type=bool).retrieve(ctx.options).value
    verbosity_five = Argument('vvvvv', type=bool).retrieve(ctx.options).value
    quiet = Argument('q', type=bool).retrieve(ctx.options).value
    if verbosity_five:
        option_handler.verbosity = 5
    elif verbosity_four:
        option_handler.verbosity = 4
    elif verbosity_two:
        option_handler.verbosity = 2
    elif verbosity_one:
        option_handler.verbosity = 1
    elif verbosity_three:  # default, must be last
        option_handler.verbosity = 3
    else:  # sth definitely went wrong
        assert False, 'No verbosity configured as default and no verbosity set!'
    if quiet:  # -q overwrites all
        option_handler.verbosity = 0


class build(FunctionDecorator):
    # TODO: implement produce=
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(Command('build', f, description='Builds the project', depends='configure'))
        found_rebuild = False
        found_configure = False
        for com in decorators.commands:
            if com.name == 'rebuild':
                found_rebuild = True
                break
            if com.name == 'configure':
                found_configure = True
                break
        if not found_configure:
            @configure
            def _configure():
                return None
        if not found_rebuild:
            # register rebuild command
            @command('rebuild', description='Cleans the project and invokes build afterwards.')
            def _rebuild():
                run_command('clean')
                run_command('build', executed_commands=['clear'])


class install(FunctionDecorator):
    # TODO: implement produce=
    def __init__(self, f):
        super().__init__(f)
        decorators.append(Command('install', f, description='Installs the project', depends='build'))
        found_build = False
        for com in decorators.commands:
            if com.name == 'build':
                found_build = True
                break
        if not found_build:
            @build
            def _build():
                return None


class configure(FunctionDecorator):
    # TODO: implement produce=
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(Command('configure', f, description='Configures the project'))


class clean(FunctionDecorator):
    # TODO: implement produce=
    def __init__(self, f):
        super().__init__(f)
        decorators.commands.append(Command('clean', f, description='Clean generated files.'))


@command('clear-cache', description='Clears the cache, deleting all recorded information.')
def _clear_cache():
    ctx.cache.clear()


@clean
def _clean():
    ret = []
    for f in ctx.builddir.glob('*', exclude='c4che'):
        ret.append(remove(f))
    for signature in signatures.values():
        signature.invalidate()
    return ret

