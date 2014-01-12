from .util import Factory


class OptionsCollection(object):
    def __init__(self, cache):
        self._cache = cache

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
        raise NotImplementedError

    def add_to_argparse(self):
        raise NotImplementedError

    @staticmethod
    def from_json(self, d):
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
