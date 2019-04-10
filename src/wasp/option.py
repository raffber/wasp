import re
from .util import Serializable, FunctionDecorator
from . import factory, decorators
from wasp.argument import ARGUMENT_KEY_RE_STR

from collections import OrderedDict


class OptionsCollection(OrderedDict):
    """
    Ordered dictionary of options. It allows adding sub-collections
    for grouping options. For examples, options for commands are grouped
    by the command names, whereas there is one top-level :class:`OptionsCollection`.
    Also, a name can be assigned to the options collection and description can be set.
    This allows ``wasp`` to show useful information to the user.

    :param name: Optional name of the collection. Will be printed to the user.
    :param description: Description of the collection. Will be printed to the user.
    """

    def __init__(self, name=None, description=None):
        super().__init__()
        self._groups = {}
        self._name = name
        self._description = description
        self._alias = {}

    def alias(self, from_, to_):
        """
        Allows specifying two sub-collection keys which map to the same
        sub-collection. Thus, two commands may accept the same options.
        """
        assert from_ not in self._alias, 'OptionsCollection '
        if to_ not in self._groups:
            self._groups[to_] = OptionsCollection(to_)
        if from_ in self._groups:
            for k, v in self._groups[from_].items():
                self._groups[to_][k] = v
        self._alias[from_] = to_

    @property
    def name(self):
        """
        Returns the name of this collection.
        """
        return self._name

    def set_description(self, desc):
        self._description = desc

    def get_description(self):
        return self._description

    description = property(get_description, set_description)

    def add(self, option):
        self[option.name] = option

    def add_to_argparse(self, args):
        """
        Adds all options and all sub-collections to the argparse
        object ``args``.

        :param args: argparse object to operated on.
        """
        subparsers = None
        for option in self.values():
            option.add_to_argparse(args)
        for name, group in self._groups.items():
            if subparsers is None:
                subparsers = args.add_subparsers(dest='command')
            groupargs = subparsers.add_parser(name)
            groupargs.required = False
            group.add_to_argparse(groupargs)
            groupargs.add_argument('other_commands', nargs="*", help='Other commands')
            # add subparser for alias as well
            for name_from, name_to in self._alias.items():
                if name_to != name:
                    continue
                groupargs = subparsers.add_parser(name_from)
                group.add_to_argparse(groupargs)
                groupargs.add_argument('other_commands', nargs="*", help='Other commands')

    def retrieve_from_dict(self, args):
        """
        Retrieves all options and all sub-collections from
        the given dict.

        :param args: The dict containing the option information.
        """
        for option in self.values():
            option.retrieve_from_dict(args)
        for name, group in self._groups.items():
            group.retrieve_from_dict(args)

    def group(self, name):
        """
        Returns a sub-collection of this collection.

        :param name: Determines which collection is to be returned.
        """
        if name in self._alias:
            name = self._alias[name]
        if name not in self._groups.keys():
            self._groups[name] = OptionsCollection(name)
        return self._groups[name]

    def remove_group(self, groupname):
        """
        Removes a sub-collection.
        """
        if groupname in self._groups.keys():
            del self._groups[groupname]

    def all(self):
        """
        Returns a dict of all options of this collection
        and all subcollections, recursively.
        """
        ret = dict(self)
        for group in self._groups.values():
            ret.update(group.all())
        return ret

    def save(self):
        """
        Saves this collection to ``ctx.cache``.
        """
        # TODO: why does this not support subcollctions
        from wasp import ctx
        d = ctx.cache.prefix('options')[self.name]
        for opt in self.values():
            d[opt.name] = opt

    def load(self, override=False):
        """
        Loads this object from ``ctx.cache``.

        :param override: Determines whether the options that are
            already present should be overwritten.
        """
        # TODO: why does this not support subcollctions
        from wasp import ctx
        d = ctx.cache.prefix('options')[self.name]
        for k, v in d.items():
            if override or k not in self.keys() or self[k].empty():
                self.add(v)


def sanitize_name(name):
    """
    Sanitizes an option name, such that it gives
    a reasonable argument name.
    """
    return name.replace('-', '_').replace(' ', '_').lower()


def name_to_key(name):
    """
    Attempts to standardize option names as used on the
    command line. (replacing ' ' by '-' atm)
    """
    return name.replace(' ', '-')


class Option(Serializable):
    """
    Abstract base class for representing command line options. It provides a more
    object-oriented interface to argument parsing than the standard python argparse,
    but the argparse module is used internally.

    :class:`Option` objects are added during the startup of ``wasp`` using the
    ``@options`` decorator. Options are added to :class:`OptionsCollection` objects
    and can be grouped. For example, each command has its own group (named after
    the command).

    After the options are added, the command line is parsed and the :class:`OptionsCollection`
    is filled with the values from the command line. It is then stored in ``ctx.options``, from
    where it may be accessed at any later stage during the execution of ``wasp``. There
    exists a special decorator called ``@handle_options`` which is called directly after
    options parsing and can be used to post-process options.

    Furthermore, :class:`Option` is a subclass of :class:`wasp.util.Serializable` and may thus
    be saved to disk, such that the values can be stored accross multiple launches of ``wasp``.

    :param name: Name of the option.
    :param description: Description of this option. To be printed to the user.
    :param keys: ``str`` or list of ``str`` which is used as the argument on the command line.
        If None, the key is inferred from the name of the option.
    :param value: Initial value (also default value) of the option.
    :param prefix: Prefix on the command line. If None, '-' is used for single letter
        keys and '--' for keys with multiple letters. If given as list, it must have
        the same length as ``keys``.
    """
    def __init__(self, name, description, keys=None, value=None, prefix=None):
        assert isinstance(name, str), 'name must be a string'
        assert isinstance(description, str), 'Description must be a string'
        self._name = sanitize_name(name)
        if keys is None:
            keys = [name_to_key(name)]
        assert isinstance(keys, list) or isinstance(keys, str), 'Keys must either be given as a string or list thereof'
        self._keys = keys
        self._description = description
        self._value = None
        self.value = value  # such that property.setter can be overridden
        self._prefix = []
        self._default = value
        if isinstance(prefix, str):
            self._prefix = [prefix]
        elif isinstance(prefix, list):
            self._prefix = prefix
        for key in self._keys:
            if len(key) == 1 and prefix is None:
                self._prefix.append('-')
            elif prefix is None:
                self._prefix.append('--')
        if len(self._prefix) == 1 and len(self._keys) > 1:
            self._prefix *= len(self._keys)
        assert len(self._prefix) == len(self._keys)

    @property
    def name(self):
        """
        Returns the name of the option. This name is also used as
        the argument name when creating an argument from this option.
        """
        return self._name

    def set_value(self, v):
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)
    """
    Gets or sets the value of this option.
    """

    @property
    def key(self):
        """
        Returns the keys which are used on the command line.
        """
        return self._keys

    @property
    def description(self):
        """
        Returns the description of this option. This is printed as
        help text to the user.
        """
        return self._description

    def add_to_argparse(self, args):
        """
        Must be overwritten. Adds the option to an ``Argparse`` object.

        :param args: ``Argparse`` object the option should use.
        """
        raise NotImplementedError

    def retrieve_from_dict(self, args):
        """
        Must be overwritten. Retrives the value of this option
        from the dict ``args`` as created by the ``argparse`` module.
        """
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        return cls(d['name'], d['description'], value=d['value'], key=d['key'], prefix=d['prefix'])

    def to_json(self):
        ret = super().to_json()
        ret.update({
            'name': self._name,
            'key': self._keys,
            'description': self._description,
            'value': self.value,
            'prefix': self._prefix})
        return ret

    def empty(self):
        """
        Returns True if the currently set value is the same as the default value.
        """
        return self._value == self._default


class ArgumentOption(Option):
    """
    Option of the form ``--key argkey=argvalue``, where the key value pair
    is converted into an :class:`wasp.argument.Argument` and returned as
    an :class:`wasp.argument.ArgumentCollection`. If multiple key-value pairs are given
    (e.g. ``--key argkey=argvalue  --key argkey2=argvalue2``) these values are all
    added to the :class:`wasp.argument.ArgumentCollection`.
    """

    KEY_VALUE_RE = re.compile('^(?P<arg_key>' + ARGUMENT_KEY_RE_STR + ')=[\"\']?(?P<arg_value>.*?)[\"\']?$')

    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, action='append'
                          , help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        from .argument import ArgumentCollection, Argument
        vlst = args.get(self.name, None)
        self.value = ArgumentCollection()
        if vlst is None:
            return
        assert isinstance(vlst, list), 'Value must be a list or None.'
        for v in vlst:
            m = self.KEY_VALUE_RE.match(v)
            if not m:
                raise ValueError('Invalid command line string: `{0}`'.format(v))
            arg_value = m.group('arg_value')
            arg_key = m.group('arg_key')
            self.value.add(Argument(arg_key).assign(arg_value))

    def set_value(self, value):
        from .argument import ArgumentCollection
        assert value is None or isinstance(value, ArgumentCollection), \
            'Invalid argument for ArgumentOption(): value ' \
            'expected to be either None or of type ArgumentCollection()'
        if value is None:
            self._value = ArgumentCollection()
        else:
            self._value = value

    value = property(Option.get_value, set_value)


class FlagOption(Option):
    """
    Option which is treated as a flag if it is specified on the command
    line, i.e. True is stored if the option is given.
    """
    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, action='store_true', default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        self.value = args.get(self.name, None)

    def set_value(self, v):
        if v is None:
            v = False
        assert isinstance(v, bool), 'Value must be a bool'
        self._value = v

    def get_value(self):
        if self._value is None:
            return False
        return self._value

    value = property(get_value, set_value)


factory.register(FlagOption)


class EnableOption(Option):
    """
    Option which allows enabling or disabling a feature.

    :param enable_prefix: Prefix to be added when the option should be turned on.
        e.g. if 'enable-' is given, the option can be turend on with '--enable-keyname'
    :param disable_prefix: Prefix to be added when the option should be turned off.
    """
    def __init__(self, *args, enable_prefix='enable-', disable_prefix='disable-', **kw):
        super().__init__(*args, **kw)
        self._enable_prefix = enable_prefix
        self._disable_prefix = disable_prefix

    def add_to_argparse(self, args):
        if not self._value:
            strings = []
            for prefix, key in zip(self._prefix, self._keys):
                strings.append(prefix + self._enable_prefix + key)
            args.add_argument(*strings, action='store_true', default=False,
                              help=self._description, dest='enable-' + self.name)
        if self._value:
            strings = []
            for prefix, key in zip(self._prefix, self._keys):
                strings.append(prefix + self._disable_prefix + key)
            args.add_argument(*strings, action='store_true', default=False,
                              help=self._description, dest='disable-' + self.name)

    def retrieve_from_dict(self, args):
        enabled = args.get('enable-' + self.name, False)
        disabled = args.get('disable-' + self.name, False)
        if enabled and not self.value:
            # enabled is default so check disabled
            self._value = not disabled  # True iff disabled not set
        if disabled and self._value:
            # disabled is default so check enabled
            self._value = enabled  # True iff enabled set

    def set_value(self, v):
        if v is None:
            v = False
        assert isinstance(v, bool), 'Value must be a bool'
        self._value = v

    def get_value(self):
        if self._value is None:
            return False
        return self._value

    value = property(get_value, set_value)

    def to_json(self):
        d = super().to_json()
        d['enable_prefix'] = self._enable_prefix
        d['disable_prefix'] = self._disable_prefix
        return d

    @property
    def from_json(cls, d):
        self = super().from_json(d)
        self._enable_prefix = d['enable_prefix']
        self._disable_prefix = d['disable_prefix']
        return self


factory.register(EnableOption)


class StringOption(Option):
    """
    Option which allows setting a string (e.g. ``--key value``)
    """

    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, default=self.value,
                          nargs=1, type=str, help=self._description,
                          dest=self.name)

    def retrieve_from_dict(self, args):
        v = args.get(self.name, None)
        if isinstance(v, list):
            v = v[0]
        self.value = v

    def set_value(self, v):
        if v is None:
            self._value = None
            return
        assert isinstance(v, str), 'Value must be a str'
        self._value = v

    value = property(Option.get_value, set_value)


factory.register(StringOption)


class IntOption(Option):
    """
    Option which allows setting an int value (e.g. ``--key 3``)
    """

    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, nargs=1, type=int, default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        v = args.get(self.name, None)
        if isinstance(v, list):
            v = v[0]
        self.value = v

    def set_value(self, v):
        if v is None:
            self._value = None
            return
        assert isinstance(v, int), 'Value must be a int'
        self._value = v

    value = property(Option.get_value, set_value)

factory.register(IntOption)


class options(FunctionDecorator):
    """
    Decorator for registring a function as source for
    command line options. The function takes exactly one argument,
    which is of type :class:`wasp.argument.OptionsCollection` and is
    expected to fill it with :class:`Option` objects.
    """
    def __init__(self, f):
        super().__init__(f)
        decorators.options.append(f)
        self.f = f


class handle_options(FunctionDecorator):
    """
    Decorator for registring a function as an options handler.
    The function is called after the options have been parsed and
    may be used to postprocess information gathered after command
    line parsing.
    """
    def __init__(self, f):
        super().__init__(f)
        decorators.handle_options.append(f)
