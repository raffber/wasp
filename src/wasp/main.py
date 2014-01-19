from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .task import SerializableTaskResult, Check
from .command import CommandFailedError
import argparse
from . import ctx
import sys


class CommandAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not '_commands' in namespace:
            setattr(namespace, '_commands', [])
        previous = namespace.ordered_args
        previous.append((self.dest, values))
        setattr(namespace, '_commands', previous)


def handle_options():
    arg = argparse.ArgumentParser(description='Welcome to {0}'.format(ctx.projectname))
    for com in decorators.commands:
        ctx.commands.append(com)
        # TODO: nicify this by sorting the default commands in a logical sequence
        # i.e. add configure before build and install
        arg.add_argument(com.name, help=com.description, action=CommandAction)
    for option_fun in decorators.options:
        option_fun(ctx.options)
    ctx.options.add_to_argparse(arg)
    if 'configure' in sys.argv:
        for config_fun in decorators.configure_options:
            config_fun(ctx.configure_options)
        ctx.configure_options.add_to_argparse(arg)
    parsed = arg.parse_args()
    ctx.options.retrieve_from_dict(vars(parsed))
    if 'configure' in sys.argv:
        ctx.configure_options.retrieve_from_dict(vars(parsed))
    return parsed


def create_context(module):
    if decorators.create_context is not None:
        context = decorators.create_context()
        assert isinstance(context, Context), 'create_context: You really need to provide a subclass of wasp.Context'
    else:
        if not hasattr(module, 'PROJECTNAME'):
            projname = 'myproject'
        else:
            projname = getattr(module, 'PROJECTNAME')
        context = Context(projname)
    import wasp
    object.__setattr__(wasp.ctx, "_obj", context)


def handle_commands(options):
    str_commands = []
    if 'commands' in options:
        str_commands = options.commands
    commands_to_run = []
    for scom in str_commands:
        for com in ctx.commands:
            if com.name == scom:
                commands_to_run.append(com)
    command_groups = []
    cur_name = None
    for com in commands_to_run:
        if cur_name != com.name:
            if cur_lst is not None:
                command_groups.append(cur_lst)
            cur_lst = []
            cur_name = com.name
        cur_lst.append(com)
    if cur_lst is not None:
        command_groups.append(cur_lst)
    for group in command_groups:
        name = None
        for com in group:
            name = com.name
            tasks = com.run()
            ctx.tasks.extend(tasks)
        results = ctx.run_tasks()
        for res in results:
            if not res.success:
                # TODO: cancel properly
                print('{0} failed'.format(com.name))
                raise CommandFailedError
            else:
                if isinstance(res, Check):
                    ctx.checks.add(res)
                else:
                    ctx.results.add(res)
        serialized_results = ctx.results.to_json()
        serialized_checks = ctx.results.to_json()
        serialized = {'results': serialized_results, 'checks': serialized_checks}
        ctx.cache.set('results', name, serialized)


def run_file(fpath):
    module = load_module_by_path(fpath)
    create_context(module)
    ctx.load()
    for hook in decorators.init:
        hook()
    parsed = handle_options()
    handle_commands(parsed)
    ctx.save()
    print('DONE')


def recurse_file(fpath):
    load_module_by_path(fpath)