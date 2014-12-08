from .util import Serializable
from . import factory
from .decorators import decorators, FunctionDecorator


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
        raise NotImplementedError

    def group(self, groupname):
        if groupname not in self._groups.keys():
            self._groups[groupname] = OptionsCollection()
        return self._groups[groupname]

    def remove_group(self, groupname):
        if groupname in self._groups.keys():
            del self._groups[groupname]


class Option(Serializable):
    def __init__(self, name, description, group=None):
        self._name = name
        self._description = description
        self._group = group

    @property
    def name(self):
        return self._name

    @property
    def group(self):
        return self._group

    @property
    def description(self):
        return self._description

    @property
    def typename(self):
        raise NotImplementedError

    def to_json(self):
        return {'name': self._name
                , 'description': self._description}

    def add_to_argparse(self, args):
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        return cls(d['name'], d['description'])


def sanitize_option_name(key):
    return key.replace('_', '-').replace(' ', '-')


class FlagOption(Option):
    def __init__(self, name, description, default=False):
        super().__init__(name, description)
        self._value = False
        self._default = default

    def set_value(self, v):
        assert isinstance(v, bool), 'You can only set a flag option to True or False'
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    def add_to_argparse(self, args):
        # TODO: groups are ignored for the time being.
        key = sanitize_option_name(self._key)
        args.add_option('--' + key, action='store_true', default=self._default,
                        help=self._description, dest=key)

    def from_argparse(self, args):
        key = sanitize_option_name(self._key)
        val = False
        if getattr(args, '--' + key):
            val = True
        self._value = val

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

