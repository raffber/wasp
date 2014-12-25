from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .config import Config
from .task import Task, group
from .task_collection import TaskCollection
from .tools import proxies as tool_proxies, NoSuchToolError
from .options import StringOption
from .execution import execute
from .node import make_node
from .argument import Argument
from . import recurse_files, ctx, log, extensions, FatalError
from .util import is_iterable
import argparse
import os

FILE_NAMES = ['build.py', 'build.user.py', 'BUILD', 'BUILD.user']


class NoSuchCommandError(Exception):
    pass


# TODO: remove
# class CommandAction(argparse.Action):
#
#     def __call__(self, parser, namespace, values, option_string=None):
#         if 'commands' not in namespace:
#             setattr(namespace, 'commands', [])
#         if values is None:
#             return
#         previous = namespace.commands
#         previous.append(values)
#         setattr(namespace, 'commands', previous)


class OptionHandler(object):
    def __init__(self):
        self._commands = []
        self._verbosity = 0
        self._argparse = argparse.ArgumentParser(description='Welcome to {0}'.format(ctx.meta.projectname))
        # retrieve descriptions of commands
        descriptions = {com.name: com.description for com in ctx.commands}
        # create a set of command names that can be called
        command_names = set(map(lambda x: x.name, ctx.commands))
        # TODO: check sorting, how?!
        for name in command_names:
            # add the group
            grp = ctx.options.group(name=name)
            grp.description = descriptions[name]
            grp.add(StringOption('target', 'Only produce the given target.', keys=['t', 'target']))
        # option decorators => TODO: different groups for command options
        for option_decorator in decorators.options:
            option_decorator(ctx.options)
        ctx.options.add_to_argparse(self._argparse)
        parsed = self._argparse.parse_args()
        parsed = vars(parsed)
        self._commands = [parsed['command']]
        ctx.options.retrieve_from_dict(parsed)
        self._options_dict = parsed
        for fun in decorators.handle_options:
            fun(self)

    @property
    def options_dict(self):
        return self._options_dict

    @property
    def commands(self):
        return self._commands

    @property
    def argparse(self):
        return self._argparse

    def set_verbosity(self, verbosity):
        assert isinstance(verbosity, int) and 0 <= verbosity <= 5, 'Verbosity must be between 0 and 5'
        self._verbosity = verbosity

    def get_verbosity(self):
        return self._verbosity

    verbosity = property(get_verbosity, set_verbosity)


def create_context(loaded_files, config=None):
    """
    Creates the context object (wasp.ctx) based either on the @create_context decorator (if it exists)
    or creates a default context otherwise.
    :param loaded_files: The files which are recursed into.
    :return: The created context.
    """
    if decorators.create_context is not None:
        context = decorators.create_context(config)
    else:
        metadata = config.metadata
        if decorators.metadata is not None:
            metadata = decorators.metadata()
        context = Context(recurse_files=loaded_files, meta=metadata, config=config)
    context.arguments.overwrite_merge(config.arguments)
    import wasp
    # assign context to proxy
    wasp.ctx.__assign_object(context)
    return context


def handle_no_command(options):
    """
    This function is called if no commands are to be executed.
    At the moment, this function only warns that no command is being executed.
    :param options: OptionsCollection with the options specified.
    :return: None
    """
    if ctx.config.default_command is not None:
        run_command(ctx.config.default_command)
    else:
        log.warn('Warning: wasp called without command and no default command specified.')


def run_command(name, executed_commands=None):
    """
    Runs a command specified by name. All dependencies of the command are
    executed, if they have not successfully executed before.
    :param name: The name of the command in question.
    :param executed_commands: List of commands that have already been executed.
    :return: True if the executed is successful, False otherwise
    """
    if executed_commands is None:
        executed_commands = []
    command_cache = ctx.cache.prefix('commands')
    if name in executed_commands:
        return
    found = False
    # run all dependencies
    for command in ctx.commands:
        if command.name != name:
            continue
        # run all dependencies automatically
        # if they fail, this command fails as well
        for dependency in command.depends:
            if not dependency in command_cache:
                # dependency never executed
                run_command(dependency, executed_commands=executed_commands)
            elif not command_cache[dependency]['success']:
                # dependency not executed successfully
                run_command(dependency, executed_commands=executed_commands)
    # now run the commands
    tasks_col = TaskCollection()
    for command in ctx.commands:
        if command.name != name:
            continue
        tasks = command.run()
        if is_iterable(tasks):
            if command.produce is not None:
                tasks = group(tasks).produce(command.produce)
            tasks_col.add(tasks)
        elif isinstance(tasks, Task):
            if command.produce is not None:
                tasks.produce(command.produce)
            tasks_col.add(tasks)
        elif tasks is not None:
            assert False, 'Unrecognized return value from {0}'.format(name)
        # else tasks is None, thats fine
        found = True
    for generator in ctx.generators(name).values():
        found = True
        tasks = generator.run()
        if is_iterable(tasks):
            tasks_col.add(tasks)
        elif isinstance(tasks, Task):
            tasks_col.add(tasks)
        elif tasks is not None:
            assert False, 'Unrecognized return value from {0}'.format(name)
    if not found:
        raise NoSuchCommandError('No command with name `{0}` found!'.format(name))
    # now execute all tasks
    jobs = Argument('jobs', type=int).retrieve_all(default=1).value
    produce = ctx.options.group(name)['target'].value
    if produce is not None:
        produce = make_node(produce)
    execute(tasks_col, jobs=jobs, produce=produce)
    # check all tasks if successful
    for key, task in tasks_col.items():
        if not task.success:
            log.fatal('Command `{0}` failed.'.format(name))
            ctx.cache.prefix('commands')[name] = {'success': False}
            return False
    log.info('SUCCESS: Command `{0}` executed successfully!'.format(name))
    ctx.cache.prefix('commands')[name] = {'success': True}
    return True


def handle_commands(options):
    """
    Runs all commands specified by the `options` parameter given.
    If a command fails, the method aborts.
    :param options: OptionsCollection(), the options given to wasp
    :return: True if the commands have been executed successfully.
    """
    executed_comands = []
    success = True
    for command in options.commands:
        success = run_command(command, executed_comands)
        if not success:
            break
        executed_comands.append(command)
    if len(executed_comands) == 0:
        handle_no_command(options)
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
        for path in recurse_files:
            if path in loaded_paths:
                continue
            ret.extend(load_directory(path))
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
        if os.path.exists(full_path):
            load_module_by_path(full_path)
            file_found.append(full_path)
    return file_found


def retrieve_verbosity():
    """
    Retrieves the verbosity level from the environment WASP_VERBOSITY="0" (up to 5)
    and the command line options -q/-v0 (quiet = 0) up to -vvvvv/-v5 (debug).
    default is -vvv (warn)
    :return: the verbosity level 0 <= verbosity <= 5
    """
    # TODO: ... only partially parse all the options... can argparse do this?!
    # that's difficult anyways... we certainly need to reparse the options again
    # but then ignore the result of it.
    # only accept verbosity as first argument?! => see how other people do it
    # let this go for the time being, as it's not that important. We will just miss
    # out on log.INFO and log.DEBUG messages during @create_context, @init and @options
    # after that, everything is fine
    return log.DEFAULT


def load_extensions(config):
    extensions.load_all('wasp.ext')
    for ext_name in config.extensions:
        extensions.load('wasp.ext.' + ext_name, required=True)


def load_tools():
    try:
        for proxy_name in tool_proxies:
            ctx.load_tool(proxy_name)
    except NoSuchToolError as e:
        log.fatal('Not all tools were loaded during init. Autoloading failed:')
        log.fatal(str(e))


def load_decorator_config(config):
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
        log.configure(config.verbosity)
    return config


def run(dir_path):
    """
    Runs the application from the given directory. It is assumed that:
     * The current working directory is `dir_path`,
     * the current working directory is the TOPDIR of the project,
     * this function is executed once.
    :param dir_path: The directory from which is used as TOPDIR
    :return: True if a build file was found in `dir_path`, False otherwise
    """
    try:
        # first and foremost, initialize logging
        log.configure(retrieve_verbosity())
        # load configuration from current directory
        config = Config.load_from_directory(dir_path)
        if config.verbosity is not None and log.verbosity == log.DEFAULT:
            # configuration overwrites default from command line/env
            log.configure(config.verbosity)
        # load all extensions
        load_extensions(config)
        # import all modules
        loaded_files = load_directory(dir_path)
        if len(loaded_files) == 0:
            log.fatal('No build file found. Exiting.')
            return True  # nothing was loaded, no point in continuing
        # load recursive files
        loaded_files.extend(load_recursive())
        # load/overwrite config from decorators
        config = load_decorator_config(config)
        # create the context using the files that were loaded.
        # the list is mainly required to determine if the build
        # files have changed.
        create_context(loaded_files, config=config)
    except FatalError:
        return False
    try:
        # load all command decorators into the context
        for com in decorators.commands:
            ctx.commands.append(com)
        # run all init() hooks
        for hook in decorators.init:
            hook()
        # autoload all tools that have not been loaded
        load_tools()
        # parse options
        options = OptionHandler()
        log.configure(options.verbosity)
        successs = handle_commands(options)
    except FatalError:
        successs = False
    finally:
        ctx.save()
    return successs
