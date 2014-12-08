from .decorators import decorators
import argparse
from . import ctx, options
from .options import FlagOption
from .argument import Argument
import sys


class CommandAction(argparse.Action):
    # XXX: UGH!
    def __call__(self, parser, namespace, values, option_string=None):
        if not '_commands' in namespace:
            setattr(namespace, '_commands', [])
        previous = namespace._commands
        previous.append(values)
        setattr(namespace, '_commands', previous)


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
        # TODO: check sorting
        for name in command_names:
            self._argparse.add_argument(name, help=descriptions[name], action=CommandAction, default='', nargs='?')
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
        self._commands = parsed._commands
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
        assert isinstance(verbosity, int) and verbosity >= 0 and verbosity <= 5, 'Verbosity must be between 0 and 5'
        self._verbosity = verbosity

    def get_verbosity(self):
        return self._verbosity

    verbosity = property(get_verbosity, set_verbosity)


@options
def add_builtin_options(option_collection):
    builtin_group = option_collection.group('builtin')
    builtin_group.description = 'Builtin options for wasp'
    builtin_group.add(FlagOption('q', 'Set verbosity level to 0 [QUIET]'))
    builtin_group.add(FlagOption('v', 'Set verbosity level to 1 [FATAL] <- default', default=True))
    builtin_group.add(FlagOption('vv', 'Set verbosity level to 2 [ERROR]'))
    builtin_group.add(FlagOption('vvv', 'Set verbosity level to 3 [WARN]'))
    builtin_group.add(FlagOption('vvvv', 'Set verbosity level to 4 [INFO]'))
    builtin_group.add(FlagOption('vvvvv', 'Set verbosity level to 5 [DEBUG]'))


class handle_options(object):
    def __init__(self, f):
        decorators.handle_options.append(f)


@handle_options
def handle_builtin_options(option_handler):
    verbosity_one = Argument('v', type=bool).retrieve(ctx.options)
    verbosity_two = Argument('vv', type=bool).retrieve(ctx.options)
    verbosity_three = Argument('vvv', type=bool).retrieve(ctx.options)
    verbosity_four = Argument('vvvv', type=bool).retrieve(ctx.options)
    verbosity_five = Argument('vvvvv', type=bool).retrieve(ctx.options)
    quiet = Argument('q', type=bool).retrieve(ctx.options)
    if verbosity_five:
        option_handler.verbosity = 5
    elif verbosity_four:
        option_handler.verbosity = 4
    elif verbosity_three:
        option_handler.verbosity = 3
    elif verbosity_two:
        option_handler.verbosity = 2
    elif verbosity_one:
        option_handler.verbosity = 1
    else:
        assert False, 'No verbosity configured as default and no verbosity set!'
    if quiet:
        option_handler.verbosity = 0