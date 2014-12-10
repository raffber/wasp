from .util import Serializable
from . import factory
from .decorators import decorators
from .util import FunctionDecorator


# TODO: implemnt more options


class OptionsCollection(dict):

    def __init__(self, groupname=None):
        super().__init__()
        self._groups = {}
        self._groupname = groupname

    @property
    def groupname(self):
        return self._groupname

    def add(self, option):
        self[option.name] = option

    def add_to_argparse(self, args):
        for option in self.values():
            option.add_to_argparse(args)
        for group in self._groups.values():
            group.add_to_argparse(args)

    def retrieve_from_dict(self, args):
        for option in self.values():
            option.retrieve_from_dict(args)
        for group in self._groups.values():
            group.retrieve_from_dict(args)

    def group(self, groupname):
        if groupname not in self._groups.keys():
            self._groups[groupname] = OptionsCollection()
        return self._groups[groupname]

    def remove_group(self, groupname):
        if groupname in self._groups.keys():
            del self._groups[groupname]

    def all(self):
        ret = dict(self)
        for group in self._groups.values():
            ret.update(group.all())
        return ret


def sanitize_name(name):
    return name.replace(' ', '_').lower()


def name_to_key(name):
    return name.replace('_', '_')


class Option(Serializable):
    def __init__(self, name, description, group=None):
        self._name = sanitize_name(name)
        self._key = name_to_key(self._name)
        self._description = description
        self._group = group

    @property
    def name(self):
        return self._name

    @property
    def key(self):
        return self._key

    @property
    def group(self):
        return self._group

    @property
    def description(self):
        return self._description

    def to_json(self):
        d = super.to_json()
        d.update({'name': self._name, 'description': self._description})
        return d

    def add_to_argparse(self, args):
        raise NotImplementedError

    def retrieve_from_dict(self, args):
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        return cls(d['name'], d['description'])


class FlagOption(Option):
    def __init__(self, name, description, prefix=None, default=False):
        super().__init__(name, description)
        self._value = False
        self._default = default
        if len(self.key) == 1 and prefix is None:
            prefix = '-'
        elif prefix is None:
            prefix = '--'
        self._prefix = prefix

    def set_value(self, v):
        assert isinstance(v, bool), 'You can only set a flag option to True or False'
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    def add_to_argparse(self, args):
        # TODO: groups are ignored for the time being.
        args.add_argument(self._prefix + self.key, action='store_true', default=self._default,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        assert self.name in args, 'Option was never added to the collection and never parsed.'
        self.value = args[self.name]

    @classmethod
    def from_json(cls, d):
        return cls(str(d['name']), str(d['description']), default=bool(d['default']))

    def to_json(self):
        ret = super().to_json()
        ret['value'] = self.value
        return ret


factory.register(FlagOption)


class EnableOption(Option):
    pass


factory.register(EnableOption)


class StringOption(Option):
    pass


factory.register(StringOption)


class IntOption(Option):
    pass


factory.register(IntOption)


class options(FunctionDecorator):
    def __init__(self, f, *commands):
        super().__init__(f)
        self.commands = commands
        for com in commands:
            assert isinstance(com, str), 'commands must be given as strings'
        decorators.options.append(self)

