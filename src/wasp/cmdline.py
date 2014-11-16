from .decorators import decorators
import argparse
from . import ctx, options
from .options import FlagOption
from .arguments import Argument
import sys


class CommandAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not '_commands' in namespace:
            setattr(namespace, '_commands', [])
        previous = namespace._commands
        previous.append(values)
        setattr(namespace, '_commands', previous)


class OptionHandler(object):
    def __init__(self):
        self._verbosity = 0
        self._argparse = argparse.ArgumentParser(description='Welcome to {0}'.format(ctx.projectname))
        added_commands = []
        for com in decorators.commands:
            if com.name in added_commands:
                ctx.commands.append(com)
                continue
            added_commands.append(com.name)
            ctx.commands.append(com)
            # TODO: sort by occurance in sys.argv
            self._argparse.add_argument(com.name, help=com.description, action=CommandAction, default='', nargs='?')
        for option_decorator in decorators.options:
            if len(option_decorator.commands) != 0:
                if option_decorator.commands in sys.argv:
                    option_decorator.fun(ctx.options)
                else:
                    pass  # TODO: unused options collection! such that previous options can still be retrieved
                    # mark the retrieved options as unused and then add them to the optionscollection as well
            else:
                option_decorator.fun(ctx.options)
        ctx.options.add_to_argparse(self._argparse)
        parsed = self._argparse.parse_args()
        ctx.options.retrieve_from_dict(vars(parsed))
        self._options_dict = vars(parsed)
        for fun in decorators.postprocess_options:
            fun(self)

    @property
    def options_dict(self):
        return self._options_dict

    @property
    def argparse(self):
        return self._argparse

    def set_verbosity(self, verbosity):
        assert isinstance(verbosity, int) and verbosity >= 0 and verbosity <= 5, 'Verbosity must be between 0 and 3'
        self._verbosity = verbosity

    def get_verbosity(self):
        return self._verbosity

    verbosity = property(get_verbosity, set_verbosity)


@options
def add_builtin_options(option_collection):
    builtin_group = option_collection.group('builtin')
    builtin_group.description = 'Builtin options for wasp'
    builtin_group.add(FlagOption('q', 'Set verbosity level to 0 [QUIET]'))
    builtin_group.add(FlagOption('v', 'Set verbosity level to 1 [FATAL] <- default'))
    builtin_group.add(FlagOption('vv', 'Set verbosity level to 2 [ERROR]'))
    builtin_group.add(FlagOption('vvv', 'Set verbosity level to 3 [WARN]'))
    builtin_group.add(FlagOption('vvvv', 'Set verbosity level to 4 [INFO]'))
    builtin_group.add(FlagOption('vvvvv', 'Set verbosity level to 5 [DEBUG]'))


class handle_options(object):
    def __init__(self, f):
        decorators.handle_options.append(f)


@handle_options
def handle_builtin_options(option_handler):
    verbosity_one = Argument('v', type=bool).retrieve(ctx.options, default=True)
    verbosity_two = Argument('vv', type=bool).retrieve(ctx.options, default=False)
    verbosity_three = Argument('vvv', type=bool).retrieve(ctx.options, default=False)
    verbosity_four = Argument('vvvv', type=bool).retrieve(ctx.options, default=False)
    verbosity_five = Argument('vvvvv', type=bool).retrieve(ctx.options, default=False)
    quiet = Argument('q', type=bool).retrieve(ctx.options, default=False)
    if verbosity_five:
        option_handler.verbosity = 5
    elif verbosity_four:
        option_handler.verbosity = 4
    elif verbosity_three:
        option_handler.verbosity = 3
    elif verbosity_two:
        option_handler.verbosity = 2
    else:  # verbosity_one:
        option_handler.verbosity = 1
    if quiet:
        option_handler.verbosity = 0
    raise NotImplementedError
