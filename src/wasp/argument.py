"""
Arguments represent the primary tool for passing data between tasks.
They main class :class:`Argument` is a serializable key-value pair.
"""

from . import ctx, factory
import re
import json
from .util import Serializable, CannotSerializeError, UnusedArgFormatter, parse_assert

from itertools import chain


ARGUMENT_KEY_RE_STR = '[\w\d]+[\w\d_-]*'
"""A key of an argument must match this string"""
ARGUMENT_KEY_RE = re.compile('^' + ARGUMENT_KEY_RE_STR + '$')
"""Compiled version of :data:`wasp.argument.ARGUMENT_KEY_RE`"""


class MissingArgumentError(Exception):
    """
    Raised when an argument is expected to be present, but is missing.
    """
    pass


class ArgumentCollection(Serializable):
    """
    Provides a dict-like interface for collecting multiple :class:`Argument`
    objects. It also allows to define nested collections, such that a scope-like
    interface can be created. Scopes can be accessed either using the
    :meth:`__call__` method or using :meth:`subcollection` For example::

        col = ArgumentCollection()
        col.add(Argument('foo').assign('bar')   # creates a new argument with key
                                                # "foo" and value "bar"
        print(col['foo'].value)                 # prints "bar"
        print(col('group')['foo'].value)        # prints "bar"
        col('group')['foo'] = 'something-else'
        print(col('group')['foo'].value)        # prints "something-else"
        print(col['foo'].value)                 # prints "bar"

    ``col('group')`` returns an :class:`ArgumentCollection` object with parent
    set to ``col``. If an argument is looked up in ``col('group')`` and it is
    missing therein, the argument is retrieved from the parent collection.
    """
    def __init__(self, *args, name=None, parent=None):
        """
        Creates an :class:`ArgumentCollection` object.
        :param args: A tuple of (key, argument) tuples.
        :param name: Allows this object to be named.
        :param parent: Sets the parent of this object. Required if
        collections should be nested.
        """
        self._d = dict(args)
        self._subs = None
        self._parent = None
        self.set_parent(parent)
        self._name = None
        self.set_name(name)

    @classmethod
    def from_dict(cls, d):
        """
        Creates a new :class:`ArgumentCollection` from a dict.
        Keys are expected to be strings.
        Value can be either :class:`Argument`, in which case they are
        used as such, or any other serializable type which is then
        wrappend within an :class:`Argument`.
        """
        if d is None:
            return cls()
        ret = cls()
        for k, v in d.items():
            assert isinstance(k, str), 'Expected a dict with string keys.'
            if not isinstance(v, Argument):
                assert isinstance(v, Serializable), ''
                ret.add(Argument(k).assign(v))
            else:
                ret.add(v)
        return ret

    def dict(self):
        return {x.key: x.value for x in self.values()}

    def add(self, *args, **kw):
        for arg in args:
            self._add_single(arg)
        for key, value in kw.items():
            self._add_single(Argument(key).assign(value))

    def _add_single(self, arg):
        if isinstance(arg, Argument):
            self[arg.key] = arg
            return
        # if arg == self, we get a serious f****up and undebuggable crash, so check this
        assert (isinstance(arg, ArgumentCollection) or isinstance(arg, Argument)) and arg != self, \
                'Can only add() Argument or ArgumentCollection to ArgumentCollection'
        assert arg.name is not None, 'ArgumentCollection() must have a key, otherwise ' \
                                     'it cannot be added to ArgumentCollection'
        arg.parent = self
        self._subs[arg.name] = arg

    def __setitem__(self, key, value):
        assert isinstance(key, str), 'Key must be of type string.'
        if isinstance(value, str):
            value = Argument(key, value=value)
        assert isinstance(value, Argument), 'Can only set Argument in ArgumentCollection.__setitem__.'
        self._d.__setitem__(key, value)

    def to_json(self):
        if self.parent is not None:
            # TODO: think about how this could be implemented and if its desirable to implement it
            # to my understanding, parents should only be used for creating namespaces of ArgumentCollection.
            raise CannotSerializeError('Only objects of type ArgumentCollection without parents nor '
                                       'subcollection can be serialized. Consider using shallowcopy(),'
                                       'which returns a new object of only the items in this collection.')
        d = factory.to_json(self._d)
        d['arguments'] = [arg.to_json() for arg in self.items()]
        if self._subs is not None:
            d_subs = [x.to_json() for x in self._subs]
        else:
            d_subs = []
        d['subcollections'] = d_subs
        return d

    @classmethod
    def from_json(cls, d):
        self = cls()
        for argjson in d['arguments']:
            arg = factory.from_json(argjson)
            self.add(arg)
        for col in d['subcollections']:
            self._subs.append(factory.from_json(col))
        return self

    def __getitem__(self, key):
        key = str(key)
        # assert isinstance(key, str), 'ArgumentCollection keys ' \
        #                              'must be strings, found: {0}'.format(type(key).__name__)
        if key not in self:
            if self.parent is not None and key in self.parent:
                return self.parent[key]
            self[key] = Argument(key)
        return self._d.__getitem__(key)

    def subcollection(self, name):
        if name not in self._subs:
            self._subs.add(ArgumentCollection(parent=self))
        return self._subs[name]

    def update(self, d):
        for k, v in d.items():
            self[k] = v

    # TODO: commented because of following todo.
    # reconsider this?!
    # @property
    # def subcollections(self):
    #     # TODO: consider returning a special dict, which
    #     # makes sure that upon __setitem__, the ArgumentCollection is
    #     # assigned the correct parent, however, if this does not happen, it's
    #     # not too bad, proper lookup will just not work. Maybe this mistake is
    #     # difficult for people to figure out?!
    #     return self._subs

    def __call__(self, name):
        return self.subcollection(name)

    def get_name(self):
        return self._name

    def set_name(self, name):
        assert name is None or isinstance(name, str), 'Name of an ArgumentCollection must either be None or str.'
        self._name = name

    name = property(get_name, set_name)

    def set_parent(self, parent):
        assert parent is None or isinstance(parent, ArgumentCollection), 'Parent must either be of type ' \
                                                                         'ArgumentCollection or None'
        self._parent = parent

    def get_parent(self):
        return self._parent

    parent = property(get_parent, set_parent)

    def copy(self):
        ret = ArgumentCollection(name=self.name, parent=self.parent)
        ret.update(dict(self._d.items()))
        ret._subs.update(self._subs)
        return ret

    def shallowcopy(self):
        return self._d.copy()

    def get(self, k, d=None):
        try:
            return self.__getitem__(k)
        except KeyError:
            pass
        return d

    def items(self):
        if self.parent is None:
            return self._d.items()
        return chain(self._d.items(), self.parent.items())

    def values(self):
        if self.parent is None:
            return self._d.values()
        return chain(self._d.values(), self.parent.values())

    def keys(self):
        if self.parent is None:
            return self._d.keys()
        return chain(self._d.keys(), self.parent.keys())

    def __contains__(self, item):
        if self.parent is None:
            return self._d.__contains__(item)
        return self._d.__contains__(item) or self.parent.__contains__(item)

    def __iter__(self):
        return iter(self.keys())

    # necessary?!
    # def __len__(self):
    #     len_subs = len(self._subs) if self._subs is not None else 0
    #     return len(self._d) + len_subs

    def isempty(self):
        parent_empty = self._parent is None or self._parent.isempty()
        return (self._subs is not None and len(self._subs) == 0) or parent_empty or len(self._d) == 0

    def overwrite_merge(self, higher_priority):
        if higher_priority is None:
            return
        for k, v in higher_priority.items():
            self[k] = v

    def keep_merge(self, lower_priority):
        for k, v in lower_priority.items():
            if k not in self:
                self[k] = v

    @classmethod
    def load(cls, fpath):
        d = {}
        with open(fpath, 'r') as f:
            try:
                d = json.load(f)
            except ValueError as e:
                raise ValueError('Invalid json file `{0}`'.format(fpath))
        self = cls()
        parse_assert(isinstance(d, dict), 'json file for ArgumentCollection must start with at dictionary.')
        for k, v in d.items():
            self.add(Argument(k).assign(v))
        return self


factory.register(ArgumentCollection)


class Argument(Serializable):
    """
    Serializable object which represents a key-value pair.
    It can be created from various sources, such as environment-variables, command line options
    or manually, see the :meth:`Argument.retrieve` method for more details.
    """

    def __init__(self, key, value=None, type=None):
        self.key = key
        self.lowerkey = key.lower()
        self.upperkey = key.upper()
        self._value = None
        self._required_type = None
        self._use_type(type)
        self.set_value(value)
        m = ARGUMENT_KEY_RE.match(key)
        if not m:
            raise ValueError('Invalid argument key, expected `{0}`'.format(ARGUMENT_KEY_RE_STR))

    def to_json(self):
        d = super().to_json()
        d['value'] = factory.to_json(self._value)
        d['key'] = self.key
        return d

    @classmethod
    def from_json(cls, d):
        value = factory.from_json(d['value'])
        key = d['key']
        return cls(key, value=value, type=type(value))

    @property
    def type(self):
        return self._required_type

    def get_value(self):
        return self._value

    def _use_type(self, tp):
        assert tp is None or tp == str or \
            tp == int or tp == bool or tp == float or tp == list or tp == dict or issubclass(tp, Serializable)
        self._required_type = tp
        self.set_value(self.value)

    def set_value(self, value):
        """
        Raises: ValueError if type conversion from value to the required type is not successful.
        """
        if self._required_type is not None and value is not None:
            assert isinstance(value, self._required_type),\
                'Argument {0} must be of type {1}, but found type {2}!' \
                ''.format(self.lowerkey, self._required_type.__name__, type(value).__name__)
            self._value = (self._required_type)(value)
            return
        if self._required_type is None and value is not None:
            self._use_type(type(value))
        self._value = value

    value = property(get_value, set_value)

    def _retrieve_from_single(self, arg):
        from .metadata import Metadata
        from .config import Config
        from .environment import Environment
        from .options import OptionsCollection

        if isinstance(arg, Environment):
            # environment variable
            return arg.get(self.upperkey)
        elif isinstance(arg, OptionsCollection):
            option = arg.all().get(self.lowerkey, None)
            if option:
                return option.value
        elif isinstance(arg, dict):
            # keyword argument
            return arg.get(self.lowerkey, None)
        elif isinstance(arg, Metadata):
            return arg.get(self.lowerkey)
        elif isinstance(arg, ArgumentCollection):
            v = arg.get(self.lowerkey)
            if v is not None:
                return v.value
        elif isinstance(arg, Config):
            return self._retrieve_from_single(arg.arguments)
        elif isinstance(arg, str):
            return arg
        elif isinstance(arg, list):
            return arg
        return None

    def retrieve(self, *args, default=None):
        for a in args:
            ret = self._retrieve_from_single(a)
            if ret is not None:
                self.value = ret
                break
        if self.value is None:
            self.value = default
        return self

    def retrieve_all(self, default=None):
        self.retrieve(ctx.arguments, ctx.options, ctx.config, ctx.meta, ctx.env, default=default)
        return self

    def require_type(self, tp):
        self._required_type = tp
        self.set_value(self._value)
        return self

    @property
    def is_empty(self):
        return self.value is None

    def assign(self, value):
        self.value = value
        return self

    def __str__(self):
        return '{0} = `{1}`'.format(self.key, str(self.value))

    def __repr__(self):
        return '<Argument: {0} = `{1}`>'.format(self.key, str(self.value))


factory.register(Argument)


def format_string(string, arguments, all_required=False):
    kw = {}
    for k, v in arguments.items():
        if v.type != str:
            continue
        kw[k] = v.value
    if all_required:
        s = string.format(**kw)
    else:
        s = UnusedArgFormatter().format(string, **kw)
    return s


def find_argumentkeys_in_string(string):
    exp = re.compile('\{(?P<argkey>' + ARGUMENT_KEY_RE_STR + ')\}')
    return exp.findall(string)


def value(arg, default=None):
    if isinstance(arg, Argument):
        if not arg.is_empty:
            ret = arg.value
        else:
            ret = arg.retrieve_all().value
    else:
        assert isinstance(arg, str), 'Expected Argument or str, got `{0}`'.format(type(arg).__name__)
        ret = Argument(arg).retrieve_all().value
    if ret is None:
        return default
    return ret


def arg(arg):
    return Argument(arg)