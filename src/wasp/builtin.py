from . import options, ctx, CommandFailedError, decorators, StringOption, log
from .main import run_command
from .util import FunctionDecorator
from .commands import Command, command
from .option import FlagOption, handle_options, ArgumentOption, IntOption
from .argument import Argument
from .fs import remove
from .cache import CACHE_FILE


class init(object):
    """
    Decorator for registring a function which is executed just after
    the build-module is loaded.
    """
    def __init__(self, f):
        decorators.init.append(f)


@handle_options
def _init_default_args(options):
    """
    Initializes default arguments and retrieves
    them from the environmnet or other sources.
    """
    arg = Argument('prefix').retrieve_all()
    if arg.is_empty:
        ctx.arguments.add(arg.assign('/usr'))


@options
def _add_log_options(col):
    """
    Adds builtin options
    """
    desc_quiet = 'Set verbosity level to 0 [QUIET]'
    desc_fatal = 'Set verbosity level to 1 [FATAL]'
    desc_error = 'Set verbosity level to 2 [ERROR]'
    desc_warn = 'Set verbosity level to 3 [WARN] <- default'
    desc_info = 'Set verbosity level to 4 [INFO]'
    desc_debug = 'Set verbosity level to 5 [DEBUG]'
    col.description = 'Builtin options for wasp'
    col.add(FlagOption(name='verbosity-quiet', keys=['q', 'v0', 'vquiet']
                       , description=desc_quiet, prefix=['-', '-', '--']))
    col.add(FlagOption(name='verbosity-fatal', keys=['v', 'v1', 'vfatal']
                       , description=desc_fatal, prefix=['-', '-', '--']))
    col.add(FlagOption(name='verbosity-error', keys=['vv', 'v2', 'verror']
                       , description=desc_error, prefix=['-', '-', '--']))
    col.add(FlagOption(name='verbosity-warn', keys=['vvv', 'v3', 'vwarn']
                       , description=desc_warn, value=True, prefix=['-', '-', '--']))
    col.add(FlagOption(name='verbosity-info', keys=['vvvv', 'v4', 'vinfo']
                       , description=desc_info, prefix=['-', '-', '--']))
    col.add(FlagOption(name='verbosity-debug', keys=['vvvvv', 'v5', 'vdebug']
                       , description=desc_debug, prefix=['-', '-', '--']))
    col.add(FlagOption(name='no-pretty', description='Disable pretty printing'
                       , keys=['u', 'no-pretty', 'ugly']))
    col.add(StringOption(name='builddir', keys=['b', 'builddir'], prefix=['-', '--']
                         , description='Sets the build directory'))


@handle_options
def _handle_log_options(option_handler):
    """
    Post-process the options previously set by :func:`_add_builtin_options`.
    """
    d = ctx.options.all()

    def retrieve(flag):
        return d[flag].value
    verbosity_one = retrieve('verbosity-fatal')
    verbosity_two = retrieve('verbosity-error')
    verbosity_three = retrieve('verbosity-warn')
    verbosity_four = retrieve('verbosity-info')
    verbosity_five = retrieve('verbosity-debug')
    quiet = retrieve('verbosity-quiet')
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


@options
def _add_options(col):
    col.add(ArgumentOption(name='arguments', keys=['d', 'define'],
                           description='Adds arguments to ctx.arguments. E.g. -d cflags="-g -O0"'))
    col.add(IntOption(name='jobs', keys=['j', 'jobs'], description='Specify number of jobs to run in parallel.'))


@handle_options
def _handle_argument_options(option_handler):
    ctx.arguments.overwrite_merge(ctx.options['arguments'].value)


class build(FunctionDecorator):
    """
    Decorator for registring a build command.
    Also adds a description and marks the `build` command
    as a dependency of the `configure` commmand.
    Furthermore, `configure` and `rebuild` commands are added.
    """
    def __init__(self, f):
        super().__init__(f)
        produce = ':def/' + f.__name__
        decorators.commands.append(Command('build', f, description='Builds the project'
                                           , depends='configure', produce=produce))
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
            @command('rebuild', description='Cleans the project and invokes build afterwards.', option_alias='build')
            def _rebuild():
                succ = run_command('clean')
                if not succ:
                    raise CommandFailedError
                succ = run_command('build', executed_commands=['clear'])
                if not succ:
                    raise CommandFailedError


class install(FunctionDecorator):
    """
    Function decorator for registring an `install` command,
    which depends on `build` and is supposed to install the project.
    """
    def __init__(self, f):
        super().__init__(f)
        produce = ':def/' + f.__name__
        decorators.commands.append(Command('install', f, description='Installs the project', depends='build', produce=produce))
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
    """
    Function decorator for registring a `configure` command.
    """
    def __init__(self, f):
        super().__init__(f)
        produce = ':def/' + f.__name__
        decorators.commands.append(Command('configure', f,
                                           description='Configures the project',
                                           produce=produce,
                                           skip_as_depenency=True))


class clean(FunctionDecorator):
    """
    Function decorator for registring a `clean` command.
    """
    def __init__(self, f):
        super().__init__(f)
        produce = ':def/' + f.__name__
        decorators.commands.append(Command('clean', f, description='Clean generated files.', produce=produce))


@command('clear-cache', description='Clears the cache, deleting all recorded information.')
def _clear_cache():
    """
    Clears all items in the cache.
    """
    ctx.cache.clear()
    # make sure topdir is kept
    ctx.cache.prefix('ctx')['topdir'] = ctx.topdir.path


@clean
def _clean():
    """
    Default implementation of the `clean` command.
    Delete everything within the `build` directory.
    """
    cache_exculde = CACHE_FILE
    yield remove(ctx.builddir.glob('.*', exclude=cache_exculde, recursive=False, dirs=True), recursive=True)
    ctx.signatures.invalidate_all()
    _clear_cache()


def alias(from_, to_):
    """
    Binds a command with name ``from`` to the command with name ``to``.
    Executing ``from`` is equivalent to executing ``to``.
    """
    description = None
    for com in decorators.commands:
        if com.name == to_:
            description = com.description

    @command(from_, description=description, option_alias=to_)
    def _from():
        from .main import run_command
        run_command(to_)


@command('diff')
def _diff():
    thislog = log.clone().configure(verbosity=log.INFO)
    for ns in ctx.produced_signatures.namespaces:
        for k, v in ctx.produced_signatures.get_signatures(ns=ns).items():
            new_sig = v.clone()
            new_sig.refresh()
            if v.value != new_sig.value:
                thislog.log_info('Signature of `{0}` changed since last run.'.format(v.key))

