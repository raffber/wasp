from .util import Serializable
from . import factory
from .decorators import decorators


# TODO: implemnt more options
# TODO: implement group


class OptionsCollection(dict):

    def add(self, option):
        self[option.name] = option

    def add_to_argparse(self, args):
        raise NotImplementedError

    def retrieve_from_dict(self, args):
        raise NotImplementedError

    def group(self, groupname):
        raise NotImplementedError

    def remove_group(self, groupname):
        raise NotImplementedError


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
        Option.__init__(name, description)
        self._value = False
        self._default = default

    def set_value(self, v):
        assert isinstance(v, bool), 'You can only set a flag option to True or False'
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    def add_to_arparse(self, args):
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


class options(object):
    def __init__(self, *commands):
        for com in commands:
            assert isinstance(com, str), 'commands must be given as strings'
        self.commands = commands
        self.fun = None

    def __call__(self, f):
        decorators.options.append(self)
        self.fun = f
        return f
