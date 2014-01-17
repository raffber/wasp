from .util import load_module_by_path
from .decorators import decorators
from .context import Context
from .command import Command
import argparse
from . import ctx
import wasp
import sys


class CommandAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not '_commands' in namespace:
            setattr(namespace, '_commands', [])
        previous = namespace.ordered_args
        previous.append((self.dest, values))
        setattr(namespace, '_commands', previous)


def run_file(fpath):
    # TODO: separate this into multiple function
    module = load_module_by_path(fpath)
    if decorators.create_context is not None:
        context = decorators.create_context()
        assert isinstance(context, Context), 'create_context: You really need to provide a subclass of wasp.Context'
    else:
        if not hasattr(module, 'PROJECTNAME'):
            projname = 'myproject'
        else:
            projname = getattr(module, 'PROJECTNAME')
        context = Context(projname)
    object.__setattr__(wasp.ctx, "_obj", context)
    for hook in decorators.init:
        hook()
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
    str_commands = []
    if 'commands' in parsed:
        str_commands = parsed.commands
    commands_to_run = []
    for scom in str_commands:
        for com in ctx.commands:
            if com.name == scom:
                commands_to_run.append(com)
    # TODO: group tasks by command name
    for com in commands_to_run:
        tasks = com.run()
        ctx.tasks.extend(tasks)
        results = ctx.run_tasks()
        for res in results:
            if not res.success:
                # TODO: cancel properly
                print('{0} failed'.format(com.name))
                return
    print('DONE')


def recurse_file(fpath):
    load_module_by_path(fpath)