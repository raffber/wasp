from .util import Factory
from .decorators import decorators


class OptionsCollection(object):
    def __init__(self, cache):
        self._cache = cache
        self._default_enable_require_configure = False

    def set_default_enable_require_configure(self, require_configure):
        self._default_enable_require_configure = require_configure

    def get_default_enable_require_configure(self):
        return self._default_enable_require_configure

    default_enable_require_configure = property(get_default_enable_require_configure
                                                , set_default_enable_require_configure)

    def add_option(self, option):
        pass

    def add_enable_option(self):
        pass

    def add_string_option(self):
        pass

    def add_int_option(self):
        pass

    def add_flag_option(self):
        pass

    def __getitem__(self, item):
        pass

    def __setitem__(self, key, value):
        # TODO: should this exist?
        pass

    def save_options(self):
        pass

    def load_options(self):
        pass


class Option(object):
    def __init__(self, name, description, require_configure=False):
        self._name = name
        self._description = description
        self._require_configure = require_configure

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    def set_require_configure(self, require_configure):
        self._require_configure = require_configure

    def get_require_configure(self):
        return self._require_configure

    require_configure = property(get_require_configure, set_require_configure)

    @property
    def typename(self):
        raise NotImplementedError

    def to_json(self):
        raise NotImplementedError

    def add_to_argparse(self):
        raise NotImplementedError

    @staticmethod
    def from_json(cls, d):
        assert('name' in d, 'Invalid json for options parsing! Delete cache!')
        name = d['name']
        return options_factory.create(name, **d)


options_factory = Factory(Option)


def make_option_name_compliant(key):
    return key.replace('_', '-')


class FlagOption(Option):
    pass


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