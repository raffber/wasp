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
    desc_quiet = 'Set verbosity level to 0 [QUIET]'
    desc_fatal = 'Set verbosity level to 1 [FATAL]'
    desc_error = 'Set verbosity level to 2 [ERROR]'
    desc_warn = 'Set verbosity level to 3 [WARN] <- default'
    desc_info = 'Set verbosity level to 4 [INFO]'
    desc_debug = 'Set verbosity level to 5 [DEBUG]'
    builtin_group.description = 'Builtin options for wasp'
    builtin_group.add(FlagOption('q', desc_quiet, prefix='-'))
    builtin_group.add(FlagOption('v', desc_fatal, prefix='-'))
    builtin_group.add(FlagOption('vv', desc_error, prefix='-'))
    builtin_group.add(FlagOption('vvv', desc_warn, value=True, prefix='-'))
    builtin_group.add(FlagOption('vvvv', desc_info, prefix='-'))
    builtin_group.add(FlagOption('vvvvv', desc_debug, prefix='-'))
    builtin_group.add(FlagOption('v0', desc_quiet, prefix='-'))
    builtin_group.add(FlagOption('v1', desc_fatal, prefix='-'))
    builtin_group.add(FlagOption('v2', desc_error, prefix='-'))
    builtin_group.add(FlagOption('v3', desc_warn, value=True, prefix='-'))
    builtin_group.add(FlagOption('v4', desc_info, prefix='-'))
    builtin_group.add(FlagOption('v5', desc_debug, prefix='-'))
    builtin_group.add(FlagOption('vquiet', desc_quiet))
    builtin_group.add(FlagOption('vfatal', desc_fatal))
    builtin_group.add(FlagOption('verror', desc_error))
    builtin_group.add(FlagOption('vwarn', desc_warn, value=True))
    builtin_group.add(FlagOption('vinfo', desc_info))
    builtin_group.add(FlagOption('vdebug', desc_debug))


@handle_options
def _handle_builtin_options(option_handler):
    d = ctx.options.all()

    def retrieve(flag_one, flag_two, flag_three):
        return d[flag_one].value or d[flag_two].value or d[flag_three].value
    verbosity_one = retrieve('v', 'v1', 'vfatal')
    verbosity_two = retrieve('vv', 'v2', 'verror')
    verbosity_three = retrieve('vvv', 'v3', 'vwarn')
    verbosity_four = retrieve('vvvv', 'v4', 'vinfo')
    verbosity_five = retrieve('vvvvv', 'v5', 'vdebug')
    quiet = retrieve('q', 'v0', 'vquiet')
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
        decorators.commands.append(Command('install', f, description='Installs the project', depends='build'))
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

