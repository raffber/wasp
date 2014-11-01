from .util import Factory
from .decorators import decorators


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


class Option(object):
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
        return {'key': self._key
                , 'description': self._description
                , 'type': self.typename}

    def add_to_argparse(self, args):
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        assert 'type' in d, 'Invalid json for options parsing! Delete cache!'
        type_ = d['type']
        return options_factory.create(type_, **d)


options_factory = Factory(Option)


def sanitize_option_name(key):
    return key.replace('_', '-')


class FlagOption(Option):
    def __init__(self, name, description):
        super().__init__(name, description)
        self._value = False

    def set_value(self, v):
        assert isinstance(v, bool), 'You can only set a flag option to True or False'
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    def add_to_arparse(self, args):
        key = sanitize_option_name(self._key)
        args.add_option('--' + key, action='store_true', default=False,
            help=self._description, dest=key)

    def from_argparse(self, args):
        key = sanitize_option_name(self._key)
        val = False
        if getattr(args, '--' + key):
            val = True
        self._value = val

    @classmethod
    def from_json(cls, json_dict):
        description = json_dict.get('description', None)
        assert description is not None
        key = json_dict.get('key', None)
        assert key is not None
        value = json_dict.get('value', False)
        assert value is not None
        ret = cls(key, description)
        ret.value = value
        return ret

    def to_json(self):
        ret = super().to_json()
        ret['value'] = self.value
        return ret

    @property
    def type_(self):
        return 'FlagOption'


options_factory.register(FlagOption)


class EnableOption(Option):
    pass


options_factory.register(EnableOption)


class StringOption(Option):
    pass


options_factory.register(StringOption)


class IntOption(Option):
    pass


options_factory.register(IntOption)


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
