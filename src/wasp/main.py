from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .task import Task
from .command import CommandFailedError
from .util import is_iterable
from .cmdline import OptionHandler
from . import ctx
import os


class EmptyCommandOption(object):
    pass


def create_context(module):
    if decorators.create_context is not None:
        context = decorators.create_context()
        assert isinstance(context, Context), 'create_context: You really need to provide a subclass of wasp.Context'
    else:
        recurse = []
        if hasattr(module, 'recurse'):
            recurse = getattr(module, 'recurse')
            assert isinstance(recurse, list), 'recurse must be a list of directories'
        for d in recurse:
            d = os.path.realpath(d)
            fpath = os.path.join(d, 'build.py')
            load_module_by_path(fpath)
        context = Context(recurse_files=recurse)
    import wasp
    wasp.ctx.__assign_object(context)


def handle_no_command(options):
    pass


def run_command(name, executed_commands):
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
                run_command(dependency, executed_commands)
            elif not command_cache[dependency]['success']:
                # dependency not executed successfully
                run_command(dependency, executed_commands)
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
            msg = '{0} failed'.format(name)
            # TODO: handle error message
            raise CommandFailedError(msg)
    ctx.tasks.clear()
    commands_cache = ctx.cache.prefix('commands')
    commands_cache[name] = {'success': True}


def handle_commands(options):
    executed_comands = []
    for command in options.commands:
        run_command(command, executed_comands)
        executed_comands.append(command)


def run_file(fpath):
    module = load_module_by_path(fpath)
    create_context(module)
    for com in decorators.commands:
        ctx.commands.append(com)
    for hook in decorators.init:
        hook()
    options = OptionHandler()
    handle_commands(options)
    ctx.save()
    print('DONE')


def recurse_file(fpath):
    # TODO: handle additional recurse
    load_module_by_path(fpath)