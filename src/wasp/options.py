from .util import Factory
from .decorators import decorators


class OptionsCollection(object):
    def __init__(self, cache=None):
        self._cache = cache
        self._options = {}

    def add_option(self, option):
        self._options[option.name] = option

    def __getitem__(self, item):
        return self._options[item]

    def get(self, item, *args):
        return self._options.get(item, *args)

    def save_options(self):
        pass

    def load_options(self):
        pass


class Option(object):
    def __init__(self, name, description):
        self._name = name
        self._description = description

    @property
    def name(self):
        return self._name

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

    def add_to_argparse(self):
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        assert 'type' in d, 'Invalid json for options parsing! Delete cache!'
        type_ = d['type']
        return options_factory.create(type_, **d)


options_factory = Factory(Option)


def make_option_name_compliant(key):
    return key.replace('_', '-')


class FlagOption(Option):
    def __init__(self, name, description):
        super().__init__(name, description)
        self._value = False

    def set_value(self, v):
        assert(isinstance(v, bool), 'You can only set a flag option to True or False')
        self._value = v

    def get_value(self):
        return self._value

    value = property(get_value, set_value)

    def add_to_arparse(self, args):
        key = make_option_name_compliant(self._key)
        args.add_option('--' + key, action='store_true', default=False,
            help=self._description, dest=key)

    def from_argparse(self, args):
        key = make_option_name_compliant(self._key)
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
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.options.append(f)
        return f


class configure_options(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.configure_options.append(f)
        return f