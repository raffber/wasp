from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .task import Task
from . import recurse_files
from .util import is_iterable
import argparse
from . import ctx
import os

FILE_NAMES = ['build.py', 'build.user.py', 'BUILD', 'BUILD.user']


class CommandAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        if 'commands' not in namespace:
            setattr(namespace, 'commands', [])
        if values is None:
            return
        previous = namespace.commands
        previous.append(values)
        setattr(namespace, 'commands', previous)


class OptionHandler(object):
    def __init__(self):
        self._commands = []
        self._verbosity = 0
        self._argparse = argparse.ArgumentParser(description='Welcome to {0}'.format(ctx.projectname))
        # retrieve descriptions of commands
        descriptions = {}
        for com in ctx.commands:
            descriptions[com.name] = com.description
        # create a set of command names that can be called
        command_names = set(map(lambda x: x.name, ctx.commands))
        # TODO: check sorting, how?!
        for name in command_names:
            self._argparse.add_argument(name, help=descriptions[name], action=CommandAction, default=None, nargs='?')
        for option_decorator in decorators.options:
            if len(option_decorator.commands) != 0:
                if option_decorator.commands in sys.argv:
                    option_decorator(ctx.options)
                else:
                    pass
                    # TODO: unused options collection! such that previous options can still be retrieved
                    # mark the retrieved options as unused and then add them to the optionscollection as well
            else:
                option_decorator(ctx.options)
        ctx.options.add_to_argparse(self._argparse)
        parsed = self._argparse.parse_args()
        self._commands = parsed.commands
        ctx.options.retrieve_from_dict(vars(parsed))
        self._options_dict = vars(parsed)
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


def create_context(recurse_files):
    """
    Creates the context object (wasp.ctx) based either on the @create_context decorator (if it exists)
    or creates a default context otherwise.
    :param recurse_files: The files which are recursed into.
    :return: The created context.
    """
    if decorators.create_context is not None:
        context = decorators.create_context()
        assert isinstance(context, Context), 'create_context: You really need to provide a subclass of wasp.Context'
    else:
        context = Context(recurse_files)
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
    ctx.log.warn('Warning: wasp called without command.')


def run_command(name, executed_commands=[]):
    """
    Runs a command specified by name. All dependencies of the command are
    executed, if they have not successfully executed before.
    :param name: The name of the command in question.
    :param executed_commands: List of commands that have already been executed.
    :return: True if the executed is successful, False otherwise
    """
    command_cache = ctx.cache.prefix('commands')
    if name in executed_commands:
        return
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
    for command in ctx.commands:
        if command.name != name:
            continue
        tasks = command.run()
        if is_iterable(tasks):
            ctx.tasks.add(tasks)
        elif isinstance(tasks, Task):
            ctx.tasks.add(tasks)
        elif tasks is not None:
            assert False, 'Unrecognized return value from {0}'.format(name)
        # else tasks is None, thats fine
    # now execute all tasks
    ctx.run_tasks()
    # check all tasks if successful
    for key, task in ctx.tasks.items():
        if not task.success:
            ctx.log.fatal('Command `{0}` failed.'.format(name))
            ctx.cache.prefix('commands')[name] = {'success': False}
            return False
    ctx.log.info('SUCCESS: Command `{0}` executed successfully!'.format(name))
    ctx.tasks.clear()
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


def load_configuration(dirpath):
    """
    :return: Returns a configuration object containing the configuration checked into the current directory.
    """
    pass


def run(dir_path):
    """
    Runs the application from the given directory. It is assumed that:
     * The current working directory is `dir_path`,
     * the current working directory is the TOPDIR of the project,
     * this function is executed once.
    :param dir_path: The directory from which is used as TOPDIR
    :return: True if a build file was found in `dir_path`, False otherwise
    """
    loaded_files = load_directory(dir_path)
    if len(loaded_files) == 0:
        return False  # nothing was loaded, no point in continuing
    # load recursive files
    loaded_files.extend(load_recursive())
    # create the context using the files that were loaded.
    # the list is mainly required to determine if the build
    # files have changed.
    create_context(loaded_files)
    # load all command decorators into the context
    for com in decorators.commands:
        ctx.commands.append(com)
    # run all init() hooks
    for hook in decorators.init:
        hook()
    options = OptionHandler()
    ctx.log.configure(options.verbosity)
    success = handle_commands(options)
    ctx.save()
    return True
