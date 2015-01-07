from . import decorators


class CommandFailedError(Exception):
    """
    Raised if a command fails during execution.
    """
    pass


class CommandCollection(dict):
    """
    dict-derived container for storing commands in the form
    ``{command.name: command}``.
    """
    def add(self, com):
        """
        Adds the command to the collection.
        """
        if com.name not in self:
            self[com.name] = []
        self[com.name].append(com)


class Command(object):
    """
    Creates a Command object, which requires a ``name`` and a callback function ``fun``, which generates tasks.

    :param name: Name of the command. The command can be invoked with ``./wasp <command-name>``.
    :param fun: Handler function of the command. It should return a task or a list thereof.
    :param description: Description of the command which may be shown to the user.
    :param depends: List of command names which should run prior to this command.
    :param produce: An argument to :func:``wasp.Node.make_node``. The resulting node is
        produced upon command completion.
    :param option_alias: The name of another command, this command is an alias of.
    """
    def __init__(self, name, fun, description=None, depends=None, produce=None, option_alias=None):
        self._depends = [] if depends is None else depends
        if isinstance(self._depends, str):
            self._depends = [self._depends]
        assert isinstance(self._depends, list), 'Expected string or list thereof.'
        self._name = name
        self._fun = fun
        self._description = description or name
        self._produce = produce
        self._option_alias = option_alias

    @property
    def depends(self):
        return self._depends

    @property
    def name(self):
        return self._name

    def run(self):
        return self._fun()

    @property
    def description(self):
        return self._description

    @property
    def produce(self):
        return self._produce

    @property
    def option_alias(self):
        return self._option_alias


class command(object):
    """
    Decorator for registring functions as command handlers. The same arguments as in :class:`wasp.commands.Command`
    are used.
    """
    def __init__(self, name, depends=None, description=None, produce=None, option_alias=None):
        self._name = name
        self._depends = depends
        self._description = description
        self._produce = produce
        self._option_alias = option_alias

    def __call__(self, f):
        if self._produce is not None:
            produce = self._produce
        else:
            produce = ':def-' + f.__name__
        decorators.commands.append(Command(self._name, f,
                                           description=self._description, depends=self._depends,
                                           produce=produce, option_alias=self._option_alias))
        return f
