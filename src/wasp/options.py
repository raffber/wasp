from .util import Serializable
from . import factory
from .decorators import decorators
from .util import FunctionDecorator


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

    def save(self):
        # ctx.cache.prefix('options')[groupname]
        raise NotImplementedError

    def load(self):
        # ctx.cache.prefix('options')[groupname]
        raise NotImplementedError


def sanitize_name(name):
    return name.replace(' ', '_').lower()


def name_to_key(name):
    return name.replace('-', '_')


class Option(Serializable):
    def __init__(self, name, description, key=None, value=None, prefix=None):
        # support *args and **kw such that parent constructor can be called with *args, **kw
        assert isinstance(name, str), 'name must be a string'
        assert isinstance(description, str), 'Description must be a string'
        self._name = sanitize_name(name)
        if key is None:
            key = name_to_key(self._name)
        self._key = key
        self._description = description
        self._value = None
        self.value = value # such that property.setter can be overridden
        if len(self.key) == 1 and prefix is None:
            prefix = '-'
        elif prefix is None:
            prefix = '--'
        self._prefix = prefix


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
        return self._key

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
            'key': self._key,
            'description': self._description,
            'value': self.value,
            'prefix': self._prefix})
        return ret


class FlagOption(Option):

    def add_to_argparse(self, args):
        args.add_argument(self._prefix + self.key, action='store_true', default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        assert self.name in args, 'Option was never added to the collection and never parsed.'
        self.value = args[self.name]

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

    @property
    def _enable_string(self):
        return self._prefix + self._enable_prefix + self.key

    @property
    def _disable_string(self):
        return self._prefix + self._disable_prefix + self.key

    def add_to_argparse(self, args):
        if not self._value:
            args.add_argument(self._enable_string, action='store_true', default=False,
                              help=self._description, dest='enable-' + self.name)
        if self._value:
            args.add_argument(self._disable_string, action='store_true', default=False,
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
        args.add_argument(self._prefix + self.key, type=str, action='store_true', default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        assert self.name in args, 'Option was never added to the collection and never parsed.'
        self.value = args[self.name]

    def set_value(self, v):
        if v is None:
            self._value = None
            return
        assert isinstance(v, str), 'Value must be a bool'
        self._value = v


factory.register(StringOption)


class IntOption(Option):

    def add_to_argparse(self, args):
        args.add_argument(self._prefix + self.key, nargs=1, type=int, default=self.value,
                          help=self._description, dest=self.name)

    def retrieve_from_dict(self, args):
        assert self.name in args, 'Option was never added to the collection and never parsed.'
        self.value = args[self.name]

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