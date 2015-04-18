import re
from .util import Serializable, FunctionDecorator
from . import factory, decorators, ctx
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
        d = ctx.cache.prefix('options')[self.name]
        for k, v in d.items():
            if override or k not in self.keys() or self[k].empty():
                self.add(v)


def sanitize_name(name):
    """
    Sanitizes an option name, such that it gives
    a reasonable argument name.
    """
    return name.replace(' ', '_').lower()


def name_to_key(name):
    """
    Attempts to standardize option names. (replacing '-' by '_' atm)
    """
    return name.replace('-', '_')


class Option(Serializable):
    def __init__(self, name, description, keys=None, value=None, prefix=None):
        assert isinstance(name, str), 'name must be a string'
        assert isinstance(description, str), 'Description must be a string'
        self._name = sanitize_name(name)
        if keys is None:
            keys = [name_to_key(self._name)]
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
        return self._name

    def set_value(self, v):
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    @property
    def key(self):
        return self._keys

    @property
    def description(self):
        return self._description

    def add_to_argparse(self, args):
        raise NotImplementedError

    def retrieve_from_dict(self, args):
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
        return self._value == self._default


class ArgumentOption(Option):

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


class FlagOption(Option):

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
            self._value = False
        assert isinstance(v, bool), 'Value must be a bool'
        self._value = v


factory.register(FlagOption)


class EnableOption(Option):
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
        if enabled and self.value:
            # enabled is default so check disabled
            self._value = not disabled  # True iff disabled not set
        if disabled and self._value:
            # disabled is default so check enabled
            self._value = enabled  # True iff enabled set

    def set_value(self, v):
        assert isinstance(v, bool), 'Value must be a bool'
        self._value = v

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

    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, default=self.value, help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        self.value = args.get(self.name, None)

    def set_value(self, v):
        if v is None:
            self._value = None
            return
        assert isinstance(v, str), 'Value must be a bool'
        self._value = v


factory.register(StringOption)


class IntOption(Option):

    def add_to_argparse(self, args):
        strings = []
        for prefix, key in zip(self._prefix, self._keys):
            strings.append(prefix + key)
        args.add_argument(*strings, nargs=1, type=int, default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        self.value = args.get(self.name, None)

    def set_value(self, v):
        if v is None:
            self._value = None
            return
        assert isinstance(v, int), 'Value must be a int'
        self._value = v


factory.register(IntOption)


class options(FunctionDecorator):
    def __init__(self, f):
        decorators.options.append(f)
        self.f = f


class handle_options(FunctionDecorator):
    def __init__(self, f):
        super().__init__(f)
        decorators.handle_options.append(f)