from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .task import Task
from .command import CommandFailedError
from . import ctx
import os


class EmptyCommandOption(object):
    pass


def handle_options():
    raise NotImplementedError


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
    object.__setattr__(wasp.ctx, "_obj", context)


def handle_no_command(options):
    pass


def run_command(name, executed_commands):
    command_cache = ctx.cache.getcache('commands')
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
        if isinstance(tasks, list):
            ctx.tasks.add(tasks)
        elif isinstance(tasks, Task):
            ctx.tasks.add(tasks)
        elif tasks is not None:
            assert False, 'Unrecognized return value from {0}'.format(name)
        # else tasks is None, thats fine
    deferred_tasks = [task for task in ctx.deferred(name)]
    ctx.tasks.add(deferred_tasks)
    # now execute all tasks
    results = ctx.run_tasks()
    ctx.results.add(results)
    # check all tasks if successful
    for key, task in ctx.tasks.items():
        if not task.success:
            msg = '{0} failed'.format(name)
            # TODO: handle error message
            raise CommandFailedError(msg)
    ctx.tasks.clear()
    ctx.results.save()
    commands_cache = ctx.cache.getcache('commands')
    commands_cache[name] = {'success': True}
    executed_commands.append(name)


def handle_commands(options):
    str_commands = []
    if '_commands' in options:
        str_commands = options._commands
    if len(str_commands) == 0:
        handle_no_command(options)
        return
    executed_comands = []
for command_name in str_commands:
        run_command(command_name, executed_comands)


def run_file(fpath):
    module = load_module_by_path(fpath)
    create_context(module)
    for hook in decorators.init:
        hook()

    parsed = handle_options()
    handle_commands(parsed)
    ctx.save()
    print('DONE')


def recurse_file(fpath):
    # TODO: handle additional recurse
    load_module_by_path(fpath)