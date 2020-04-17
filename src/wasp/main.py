import argparse
import os
import sys
import types
import traceback

from . import _recurse_files, ctx, log, extensions, FatalError, CommandFailedError, decorators, Directory
from . import osinfo
from .argument import value
from .config import Config
from .execution import execute, ParallelExecutor
from .node import nodes
from .option import StringOption
from .signature import FileSignature
from .task import Task, group, TaskCollection, TaskGroup
from .tools import proxies as tool_proxies, NoSuchToolError
from .util import is_iterable
from .util import load_module_by_path

BUILD_DIR = 'build'
FILE_NAMES = ['build.py', 'build.user.py', 'BUILD', 'BUILD.user']

if osinfo.windows:
    FILE_NAMES.append('build.windows.py')
elif osinfo.linux:
    FILE_NAMES.append('build.linux.py')

has_argcomplete = True
try:
    import argcomplete
except ImportError:
    has_argcomplete = False


class NoSuchCommandError(Exception):
    pass


class OptionHandler(object):
    """
    Utility class for encapuslating the parsing of all
    command line arguments.
    """
    def __init__(self):
        self._commands = []
        self._argparse = argparse.ArgumentParser(description='Welcome to {0}'.format(ctx.meta.projectname))

    def parse(self, args=None):
        """
        Injects the argument parser, adds all options to it (by calling the respective handlers),
        parses the command line and calls all ``@option_handler`` functions.
        """
        # use description if it is not None
        descriptions = {}
        command_names = set(ctx.commands.keys())
        for comname in ctx.commands:
            for com in ctx.commands[comname]:
                if com.name not in descriptions:
                    descriptions[com.name] = com.description
                elif com.description is not None:
                    descriptions[com.name] = com.description
        alias = {com.name: com.option_alias for coms in ctx.commands.values() for com in coms}
        # don't add commands with an alias to another command
        # setup OptionCollection with defined alias
        for name in command_names:
            if alias[name] is not None:
                ctx.options.alias(name, alias[name])
                continue
        # add all subparsers for
        for name in command_names:
            # ignore commands with aliases, since those would get added double
            if alias[name] is not None:
                continue
            # add the group
            grp = ctx.options.group(name=name)
            grp.description = descriptions[name]
            grp.add(StringOption('target', 'Only produce the given target.', keys=['t', 'target']))
        # call option decorators
        for option_decorator in decorators.options:
            option_decorator(ctx.options)
        # setup argument parser
        ctx.options.add_to_argparse(self._argparse)
        if has_argcomplete:
            argcomplete.autocomplete(self._argparse)
        parsed = self._argparse.parse_args(args=args)
        if 'command' not in parsed or parsed.command is None:
            extra = None
        else:
            extra = parsed.other_commands
        parsed = vars(parsed)
        ctx.options.retrieve_from_dict(parsed)
        com = parsed['command'] if 'command' in parsed else None
        if com is not None:
            self._commands = [com]
        else:
            com = ctx.config.default_command
            if com is not None:
                self._commands = [com]
            else:
                log.warn('Warning: wasp called without command and no default command specified.')
        while extra:
            more = vars(self._argparse.parse_args(extra))
            com = more['command']
            self._commands.append(com)
            ctx.options.group(com).retrieve_from_dict(more)
            extra = more['other_commands']

    def handle_options(self):
        for fun in decorators.handle_options:
            fun(self)

    @property
    def commands(self):
        """
        Returns an ordered list of all commands to be run.
        """
        return self._commands

    @property
    def argparse(self):
        """
        Returns the ArgumentParser.
        """
        return self._argparse


def retrieve_command_tasks(name):
    """
    Retrieves tasks from the command ``name``.

    :param name: Name of the command.
    :return: An object of type TaskCollection() populated with tasks.
    """
    if name not in ctx.commands:
        raise NoSuchCommandError('No command with name `{0}` found!'.format(name))
    found = False
    tasks_col = {}
    for command in ctx.commands[name]:
        tasks_col[str(command.produce)] = []
    for command in ctx.commands[name]:
        produced_name = str(command.produce)
        tasks = command.run()
        if isinstance(tasks, types.GeneratorType):
            tasks = list(tasks)
            tasks_col[produced_name].extend(tasks)
        elif is_iterable(tasks):
            tasks_col[produced_name].extend(list(tasks))
        elif isinstance(tasks, Task):
            tasks_col[produced_name].append(tasks)
        elif isinstance(tasks, TaskGroup):
            tasks_col[produced_name].extend(tasks.tasks)
        elif tasks is not None:
            assert False, 'Unrecognized return value from {0}'.format(name)
        # else tasks is None, thats fine
        found = True
    ret = TaskCollection()
    produced = set()
    for command in ctx.commands[name]:
        produce_name = str(command.produce)
        if produce_name in produced:
            continue
        produced.add(produce_name)
        tasks = tasks_col[produce_name]
        if len(tasks) == 0:
            continue
        tasks = group(tasks)
        ret.add(tasks.produce(command.produce))
    if not found:
        raise NoSuchCommandError('No command with name `{0}` found!'.format(name))
    return ret


def run_command_dependencies(name, executed_commands=None):
    """
    Runs all commands which are dependencies of the command with ``name``.

    :param name: The command for which all dependencies should be executed.
    :param executed_commands: All commands that have already been executed in this run.
    """
    if executed_commands is None:
        executed_commands = []
    if name in executed_commands:
        return
    # run all dependencies
    if name not in ctx.commands:
        raise NoSuchCommandError('No such command: `{0}`'.format(name))
    for command in ctx.commands[name]:
        # run all dependencies automatically
        # if they fail, this command fails as well
        for dependency in command.depends:
            succ = run_command(dependency, executed_commands=executed_commands)
            if not succ:
                return False
    return True


def execute_tasks(name, tasks):
    """
    Runs all tasks given by ``tasks``.

    :param name: Name of the command for which the tasks should be executed.
    :param tasks: :class:`TaskCollection` of all tasks to be executed.
    """
    ret = extensions.api.run_task_collection(tasks)
    if ret != NotImplemented:
        return ret
    jobs = value('jobs')
    if jobs is not None:
        try:
            jobs = int(jobs)
        except ValueError:
            log.error('Invalid value given for `jobs` argument. \n'
                      'Expects somethings convertible to `int`, was: `{0}`'.format(jobs))
            jobs = None
    produce = ctx.options.group(name)['target'].value
    if produce is not None:
        produce = nodes(produce)
    executor = extensions.api.create_executor(name)
    if executor == NotImplemented:
        executor = ParallelExecutor(ns=name)
    execute(tasks, executor, produce=produce, ns=name)
    if not executor.success:
        log.fatal(log.format_fail() + 'Command Failed: {0}'.format(name))
        ctx.cache.prefix('commands')[name] = {'success': False}
        return False
    log.info(log.format_success() + 'Command Completed: {0}'.format(name))
    ctx.cache.prefix('commands')[name] = {'success': True}
    return True


def run_command(name, executed_commands=None):
    """
    Runs a command specified by name. All dependencies of the command are
    executed, if they have not successfully executed before.

    :param name: The name of the command in question.
    :param executed_commands: List of commands that have already been executed.
    :return: True if the executed is successful, False otherwise
    """
    ret = extensions.api.run_command(name)
    if ret != NotImplemented:
        return ret
    extensions.api.command_started(name)
    # run all dependencies of this task
    if not run_command_dependencies(name, executed_commands=executed_commands):
        return False
    old_namespace = ctx.current_namespace
    ctx.current_namespace = name
    # now run the commands
    try:
        tasks_col = retrieve_command_tasks(name)
        extensions.api.tasks_collected(tasks_col)
        # now execute all tasks
        ret = execute_tasks(name, tasks_col)
        extensions.api.command_finished(name, ret)
    except CommandFailedError as e:
        log.fatal(log.format_fail('Command `{0}` failed: {1}'.format(name, str(e))))
        return False
    finally:
        ctx.current_namespace = old_namespace
    return ret


def handle_commands(options):
    """
    Runs all commands specified by the `options` parameter given.
    If a command fails, the method aborts.

    :param options: OptionsCollection(), the options given to wasp
    :return: True if the commands have been executed successfully.
    """
    success = True
    for command in options.commands:
        success = run_command(command)
        if not success:
            break
    return success


def load_recursive():
    """
    Loads all directorires which were defined as recursive, using
    wasp.recurse().

    :return: Returns a list of loaded files, [] if no file was loaded.
    """
    loaded = True
    loaded_paths = set()
    ret = []
    while loaded:
        loaded = False
        for path in _recurse_files:
            if path in loaded_paths:
                continue
            ret.extend(load_directory(path))
            loaded_paths.add(path)
            loaded = True
    return ret


def load_directory(dir_path):
    """
    Loads a directory and imports the files as modules, which is the only thing that
    is necessary for executing commands.

    :param dir_path: The path to the directory which contains the build files.
    :return: Returns a list of loaded files, [] if no files were loaded
    """
    file_found = []
    for fname in FILE_NAMES:
        full_path = os.path.join(dir_path, fname)
        if os.path.exists(full_path) and not os.path.isdir(full_path):
            load_module_by_path(full_path)
            file_found.append(full_path)
    return file_found


def load_files(fs):
    """
    Load a set of files as modules.
    """
    for f in fs:
        if os.path.exists(f):
            load_module_by_path(f)


def retrieve_verbosity():
    """
    Retrieves the verbosity level from the environment WASP_VERBOSITY="0" (up to 5)
    and the command line options -q/-v0 (quiet = 0) up to -vvvvv/-v5 (debug).
    default is -vvv (warn)

    :return: the verbosity level 0 <= verbosity <= 5
    """
    # retrieve from argv
    argv = sys.argv
    if '-v0' in argv or '-q' in argv or '--vquiet' in argv:
        return log.QUIET
    if '-v1' in argv or '-v' in argv or '--vfatal' in argv:
        return log.FATAL
    if '-v2' in argv or '-vv' in argv or '--verror' in argv:
        return log.ERROR
    if '-v3' in argv or '-vvv' in argv or '--vwarn' in argv:
        return log.WARN
    if '-v4' in argv or '-vvvv' in argv or '--vinfo' in argv:
        return log.INFO
    if '-v5' in argv or '-vvvvv' in argv or '--vdebug' in argv:
        return log.DEBUG
    # retrieve from environment
    name = 'WASP_VERBOSITY'
    if name not in os.environ:
        return log.DEFAULT
    value = os.environ[name]
    if value == '0' or value == 'quiet':
        return log.QUIET
    if value == '1' or value == 'fatal':
        return log.FATAL
    if value == '2' or value == 'error':
        return log.ERROR
    if value == '3' or value == 'warn':
        return log.WARN
    if value == '4' or value == 'info':
        return log.INFO
    if value == '5' or value == 'debug':
        return log.DEBUG
    log.warn('Unrecognized value of environment variable `{0}`: `{1}`'.format(name, value))
    return log.DEFAULT


def retrieve_builddir():
    """
    Retrieves and returns the build directory based on the command
    line options or based on the environment.
    """
    next = False
    builddir = BUILD_DIR
    for arg in sys.argv:
        if arg == '-b' or arg == '--builddir':
            next = True
            continue
        if next:
            return arg
    if 'BUILDDIR' in os.environ:
        return os.environ['BUILDDIR']
    return builddir


def retrieve_pretty_printing():
    """
    Retrieves whether pretty printing should be activated.
    """
    argv = sys.argv
    if '-u' in argv or '--no-pretty' in argv or '--ugly' in argv:
        return False
    return True


def load_extensions_from_config(config):
    """
    Loads extensions based on ``config`` (which may be parsed
    from ``wasprc.json``).
    """
    if config.extensions is None:
        return
    for ext_name in config.extensions:
        extensions.load('wasp.ext.' + ext_name, required=True)


def load_tools():
    """
    Loads all tools which have so far been declared with :func:`wasp.tools.tool()`
    """
    try:
        for proxy_name in tool_proxies:
            ctx.tools.load(proxy_name)
    except NoSuchToolError as e:
        log.fatal('Not all tools were loaded during init. Autoloading failed:')
        log.fatal(str(e))


def load_decorator_config(config):
    """
    Load a :class:`wasp.config.Config` object based on decorator registered functions.
    """
    # run all config decorators:
    for x in decorators.config:
        c = x()
        if c is None:
            log.warn('Empty return value from @config function. Ignoring.')
            continue
        assert isinstance(c, Config), 'Expected a return value of type Config.'
        config.overwrite_merge(c)
    if config.verbosity is not None and log.verbosity == log.DEFAULT:
        # configuration overwrites default from command line/env
        log.configure(verbosity=config.verbosity)
    ctx.config = config
    ctx.arguments.overwrite_merge(config.arguments)
    if config.metadata is not None:
        ctx.meta = config.metadata
    if decorators.metadata is not None:
        ctx.meta = decorators.metadata()
    return config


def init_context(builddir):
    """
    Initializes the global context :data:`wasp.ctx`.
    """
    ctx.builddir = builddir
    load_tools()  # this has to happen BEFORE! the context is loaded
    # because tools should be able to register themselves in factories
    ctx.load()


def check_script_signatures(loaded_files):
    """
    Checks the signatures of all build scripts which have been loaded.
    If the script signatures have changed since the last time ``wasp`` was
    executed, the cache as well as all signatures are cleared. Consequently,
    everything is built from scratch (since the build logic may have changed
    completely).

    :param loaded_files: List of file names of loaded files.
    """
    changed = False
    d = ctx.cache.prefix('script-signatures')
    current_signatures = {}
    for f in loaded_files:
        cur_sig = FileSignature(f)
        cur_sig.refresh()
        current_signatures[f] = cur_sig
    for f, cur_sig in current_signatures.items():
        if f not in d.keys():
            changed = True
            break
        old_sig = d[f]
        if cur_sig != old_sig:
            changed = True
            break
    if changed:
        ctx.cache.clear()
        ctx.produced_signatures.clear()
        if len(d) != 0:
            # don't issue warning if wasp was never run before
            log.info(log.format_info('Build scripts have changed since last execution!',
                       'All previous configurations have been cleared!'))
    d = ctx.cache.prefix('script-signatures')
    d.clear()
    d.update(current_signatures)


def run(dir_path):
    """
    Runs the application from the given directory. It is assumed that:
     * The current working directory is `dir_path`,
     * the current working directory is the TOPDIR of the project,
     * this function is executed once.

    :param dir_path: The directory from which is used as TOPDIR
    :return: True if a build file was found in `dir_path`, False otherwise
    """
    success = False
    try:
        #
        # first and foremost, initialize logging
        log.configure(verbosity=retrieve_verbosity(), pretty=retrieve_pretty_printing())
        # load configuration from current directory
        config = Config.load_from_directory(dir_path)
        extensions.api.config_loaded(config)
        if config.verbosity is not None and log.verbosity == log.DEFAULT:
            # configuration overwrites default from command line/env
            # but NOT if verbosity was modified from default
            log.configure(verbosity=config.verbosity, pretty=config.pretty)
        # load all extensions
        load_extensions_from_config(config)
        # import all modules
        extensions.api.before_load_scripts()
        # load toplevel directory
        loaded_files = load_directory(dir_path)
        files_to_load = extensions.api.find_scripts()
        load_files(files_to_load)
        if len(loaded_files) == 0 and len(files_to_load) == 0:
            log.fatal('No build file found. Exiting.')
            return True  # nothing was loaded, no point in continuing
        extensions.api.top_scripts_loaded()
        # load recursive files
        loaded_files.extend(load_recursive())
        extensions.api.all_scripts_loaded()
        # load/overwrite config from decorators
        load_decorator_config(config)
        # initialize the context
        init_context(Directory(retrieve_builddir()))
        extensions.api.context_created()
    except FatalError as e:
        e.print()
        return False
    except Exception as e:
        traceback.print_exception(None, e, e.__traceback__)
        return False
    try:
        check_script_signatures(loaded_files)
        # load all command decorators into the context
        for com in decorators.commands:
            ctx.commands.add(com)
        # run all init() hooks
        for hook in decorators.init:
            hook()
        extensions.api.initialized()
        # parse options
        options = OptionHandler()
        extensions.api.retrieve_options(ctx.options)
        options.parse()
        extensions.api.options_parsed(ctx.options)
        if 'clean' in options.commands:
            run_command('clean')
        options.handle_options()
        success = handle_commands(options)
    except FatalError as e:
        e.print()
        success = False
    except Exception as e:
        traceback.print_exception(None, e, e.__traceback__)
    ctx.save()
    return success
