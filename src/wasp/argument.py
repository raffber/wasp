"""
Arguments represent the primary tool for passing data between tasks.
They main class :class:`Argument` is a serializable key-value pair.
"""

from . import ctx, factory
import re
import json
from .util import Serializable, UnusedArgFormatter, parse_assert, is_json_primitive


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
    def __init__(self, *args, parent=None):
        """
        Creates an :class:`ArgumentCollection` object.
        :param args: A tuple of (key, argument) tuples.
        :param name: Allows this object to be named.
        :param parent: Sets the parent of this object. Required if
        collections should be nested.
        """
        self._d = dict(args)
        self._subs = {}
        self._parent = None
        self.set_parent(parent)
        self._key = None

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
                assert isinstance(v, Serializable) or is_json_primitive(v), ''
                ret.add(Argument(k).assign(v))
            else:
                ret.add(v)
        return ret

    def dict(self):
        """
        :return: A dict with ``{argument.key: argument.value}``
        """
        return {x.key: x.value for x in self.values()}

    def add(self, *args, **kw):
        """
        Adds arguments to the collection. Arguments can either be given in \*args, or
        they can be specified using keyword arguments. Example::

            In [1]: foo = Argument('foo').assign('foo')
            In [2]: bar = Argument('bar').assign('bar')
            In [3]: col = ArgumentCollection()
            In [4]: col.add(foo, bar, foobar='test')
            In [5]: col
            Out[5]: {foo = foo, foobar = test, bar = bar}
        """
        for arg in args:
            self._add_single(arg)
        for key, value in kw.items():
            self._add_single(Argument(key).assign(value))

    def _add_single(self, arg):
        """
        Adds a single Argument.
        :param arg: non-None object of type Argument.
        """
        assert arg is not None
        self[arg.key] = arg

    def __setitem__(self, key, value):
        """
        Sets self[key] to Argument(key, value=value).
        Otherwise self[key] is set to to value and value is expected to be of type Argument.
        """
        key = str(key)
        if is_json_primitive(value):
            value = Argument(key, value=value)
        assert isinstance(value, Argument), 'Can only set Argument in ArgumentCollection.__setitem__.'
        self._d.__setitem__(key, value)

    def to_json(self):
        """
        Overrides Serializable.to_json(). Returns a dict.
        NOTE: The parent of self is not serialized. If a hierarchy should
        be serialized, use the top-most object for serialization.
        """
        # if self.parent is not None:
        #     # TODO: think about how this could be implemented and if its desirable to implement it
        #     # to my understanding, parents should only be used for creating namespaces of ArgumentCollection.
        #     raise CannotSerializeError('Only objects of type ArgumentCollection without parents nor '
        #                                'subcollection can be serialized. Consider using shallowcopy(),'
        #                                'which returns a new object of only the items in this collection.')
        d = super().to_json()
        # d.update(factory.to_json(self._d))
        d['arguments'] = [arg.to_json() for arg in self._d.values()]
        d_subs = {k: v.to_json() for k, v in self._subs.items()}
        d['subcollections'] = d_subs
        return d

    @classmethod
    def from_json(cls, d):
        """
        Restores an ArgumentCollection object from a json-dict.
        """
        self = cls()
        for argjson in d['arguments']:
            arg = factory.from_json(argjson)
            self.add(arg)
        for k, v in d['subcollections'].items():
            self._subs[k] = factory.from_json(v)
        return self

    def __getitem__(self, key):
        """
        Returns the Argument associated with key.
        If key is not found in self and self is assigned a parent, the
        Argument is looked-up therein.
        Otherwise, an empty argument is created and returned.
        """
        key = str(key)
        if key not in self:
            if self.parent is not None and key in self.parent:
                return self.parent[key]
            self[key] = Argument(key)
        return self._d.__getitem__(key)

    def subcollection(self, name):
        """
        Adds a child-collection to this ArgumentCollection and returns it.
        """
        if name not in self._subs:
            self._subs[name] = ArgumentCollection(parent=self)
        return self._subs[name]

    def update(self, d):
        """
        Updates self with the key-value pairs found in d.
        See :meth:`ArgumentCollection.__setitem__` for more details.
        """
        for k, v in d.items():
            self[k] = v

    def value(self, key):
        """
        Returns the value of the argument of self[key].
        If key not in self, return None.
        """
        arg = self.get(key)
        if arg is None:
            return None
        return arg.value

    def __call__(self, name):
        """Equivalent to self.subcollection(name)"""
        return self.subcollection(name)

    def set_parent(self, parent):
        assert parent is None or isinstance(parent, ArgumentCollection), 'Parent must either be of type ' \
                                                                         'ArgumentCollection or None'
        self._parent = parent

    def get_parent(self):
        return self._parent

    parent = property(get_parent, set_parent)

    def copy(self):
        """
        Copy self, such that it can be modified without modifying the
        original collection. The tree of subcollections is copied
        recursively.
        """
        ret = ArgumentCollection(parent=self.parent)
        ret.update(dict(self._d.items()))
        for k, v in self._subs.items():
            new_subcol = v.copy()
            ret._subs[k] = new_subcol
        return ret

    def get(self, k, d=None):
        """
        :return: ``d`` if ``k`` not in self, self[k] otherwise.
        """
        if k not in self:
            return d
        return self.__getitem__(k)

    def items(self):
        """
        :return: An iterator of (key, argument) which iterates over all arguments in self and self.parent.
        """
        for k, v in self._d.items():
            yield k, v
        if self.parent is not None:
            for k, v in self.parent.items():
                if k in self._d:
                    continue
                yield v

    def values(self):
        """
        :return: An iterator of argument which iterates over all arguments in self and self.parent.
        """
        for x in self._d.values():
            yield x
        if self.parent is not None:
            for k, v in self.parent.items():
                if k in self._d:
                    continue
                yield v

    def keys(self):
        """
        :return: An iterator of key which iterates over all arguments in self and self.parent.
        """
        for x in self._d.keys():
            yield x
        if self.parent is not None:
            for k in self.parent:
                if k in self._d:
                    continue
                yield k

    def __contains__(self, key):
        """
        Checks if self or self.parent contains an argument identified
        by ``key``.
        """
        if self.parent is None:
            return self._d.__contains__(key)
        return self._d.__contains__(key) or self.parent.__contains__(key)

    def __iter__(self):
        """Same as self.keys()"""
        return iter(self.keys())

    def isempty(self):
        """
        :return: True if self and self.parent is empty, i.e. no items can be accessed.
        """
        parent_empty = self._parent is None or len(self._parent) == 0
        #subs_empty = self._subs is None or len(self._subs) == 0
        return parent_empty and len(self._d) == 0  # and subs_empty

    def overwrite_merge(self, higher_priority):
        """
        Merge ``higher_priority`` into  self. If the key is already contained in self,
        overwrite the value of self.
        """
        if higher_priority is None:
            return
        for k, v in higher_priority.items():
            self[k] = v

    def keep_merge(self, lower_priority):
        """
        Merge ``lower_priority`` into  self. If the key is already contained in self,
        keep the value of self.
        """
        for k, v in lower_priority.items():
            if k not in self:
                self[k] = v

    @classmethod
    def load(cls, fpath):
        """
        Loads the ArgumentCollection from a json file on the disc.
        """
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

    def __repr__(self):
        return '{' + ', '.join('{0} = {1}'.format(k, v.value) for k, v in self.items()) + '}'


factory.register(ArgumentCollection)


class Argument(Serializable):
    """
    Serializable object which represents a key-value pair.
    It can be created from various sources, such as environment-variables, command line options
    or manually, see the :meth:`Argument.retrieve` method for more details.
    The Argument remembers they type of its first assigned value. Assigning another type requires
    changing the type settings. Attempting to set a value with different type will trigger
    an AssertionError.
    """

    def __init__(self, key, value=None, type=None):
        """
        Creats a new Argument with a given key. If value and/or type arguments are present,
        the value/type of this Argument will be set.
        :param key: Expected to be a string with length > 0 and match ARGUMENT_KEY_RE.
        :param value: If value is given, it will be immediately assigned to self. if type is None,
        the type(value) will be used.
        :param type: Sets the required type of the argument.
        """
        self.key = key
        assert isinstance(key, str) and len(key) > 0
        self._lowerkey = key.lower()
        self._upperkey = key.upper()
        self._value = None
        self._required_type = None
        self.set_value(value)
        if type is not None:
            self._use_type(type)
        m = ARGUMENT_KEY_RE.match(key)
        if not m:
            raise ValueError('Invalid argument key, expected `{0}`, found: `{1}`'.format(ARGUMENT_KEY_RE_STR, key))

    def to_json(self):
        d = super().to_json()
        d['value'] = factory.to_json(self._value)
        d['key'] = self.key
        return d

    @property
    def lowerkey(self):
        """
        same as self.key.lower()
        """
        return self._lowerkey

    @property
    def upperkey(self):
        """
        same as self.key.upper()
        """
        return self._upperkey

    @classmethod
    def from_json(cls, d):
        value = factory.from_json(d['value'])
        key = d['key']
        return cls(key, value=value, type=type(value))

    @property
    def type(self):
        """
        :return: The type of the value of this Argument. Returns None if the arguent was never assigned
            any value.
        """
        return self._required_type

    def _use_type(self, tp):
        assert tp is None or tp == str or \
            tp == int or tp == bool or tp == float or tp == list or tp == dict or issubclass(tp, Serializable)
        self._required_type = tp
        self.set_value(self.value)

    def get_value(self):
        return self._value

    def set_value(self, value):
        """
        Assigns ``value`` to self.value. If a type has already been set before, the new value
        must conform to the requirements of it (i.e. isinstance(value, type) must be True).
        Raises: TypeError if type conversion from value to the required type is not successful.
        """
        if self._required_type is not None and value is not None:
            if not isinstance(value, self._required_type):
                raise TypeError('Argument {0} must be of type {1}, but found type {2}!'.format(
                    self.lowerkey, self._required_type.__name__, type(value).__name__))
            # self._value = (self._required_type)(value)
            self._value = value
            return
        if self._required_type is None and value is not None:
            self._use_type(type(value))
        self._value = value

    value = property(get_value, set_value)

    def _retrieve_from_single(self, arg):
        """
        see :meth:`Argument.retrieve`.
        """
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
            return arg.get(self.key, None)
        elif isinstance(arg, Metadata):
            return arg.get(self.key)
        elif isinstance(arg, ArgumentCollection):
            v = arg.get(self.key)
            if v is not None:
                return v.value
        elif isinstance(arg, Config):
            return self._retrieve_from_single(arg.arguments)
        elif isinstance(arg, Serializable) or isinstance(arg, list) or is_json_primitive(arg):
            return arg
        return None

    def retrieve(self, *args, default=None):
        """
        Retrieve the value of self from various sources.
        If multiple arguments are given, the value is retrieved
        from the first source, in which it was found.
        Possible sources are:

         * Environment (ctx.env, self.upperkey is used for retrieval)
         * OptionsCollection (ctx.options, self.lowerkey is used for retrieval)
         * a dict where key is used to retrive the value.
         * Metadata (can contain key-value pairs))
         * ArgumentCollection
         * Config (which contains an arguments section)
         * Serializable or primitive or list is assigned to the argument

        If the argument is not found in any given source, it's value is not set
        and thus None.

        :param default: Default value which is assigned, if the value was not found.
        :return: self
        """
        for a in args:
            ret = self._retrieve_from_single(a)
            if ret is not None:
                self.value = ret
                break
        if self.value is None:
            self.value = default
        return self

    def retrieve_all(self, default=None):
        """
        Retrieves the value of the Argument from:

         * ctx.arguments
         * ctx.options
         * ctx.config
         * ctx.meta
         * ctx.env

        The order defines the priority in which the various sources are considered.

        :param default: Default value which is assigned, if the value was not found.
        :return: self
        """
        self.retrieve(ctx.arguments, ctx.options, ctx.config, ctx.meta, ctx.env, default=default)
        return self

    def require_type(self, tp):
        """
        Sets the type of the Argument to tp. If the value does
        not conform to the type specified, a ValueError is raised.

        :param tp: asdf
        :return: self
        """
        self._required_type = tp
        self.set_value(self._value)
        return self

    @property
    def is_empty(self):
        """
        :return: True if self.value is None, False otherwise
        """
        return self.value is None

    def assign(self, value):
        """
        Assigns the value to self.

        :return: self
        """
        self.value = value
        return self

    def __str__(self):
        return '{0} = `{1}`'.format(self.key, str(self.value))

    def __repr__(self):
        return '<Argument: {0} = `{1}`>'.format(self.key, str(self.value))


factory.register(Argument)


def format_string(string, arguments, all_required=False):
    """
    Similiar to str.format. Formats a string using the values given in
    an argumentcollection. Example::

        In [1]: col = ArgumentCollection()
        In [2]: col['foo'] = 'bar'
        In [3]: col
        Out[3]: {foo = bar}
        In [4]: format_string('This is foo{foo}', col)
        Out[4]: 'This is foobar'

    :param string: String to be formatted. Use {argumentkey} for specifying the destination
        where the argument should be inserted.
    :param arguments: ArgumentCollection with values used for formatting the string.
    :param all_required: Defines whether a KeyError is raised if not all tags in
        the format string were found in arguments.
    :return: The formatted string.
    """
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
    """
    :return: Returns all argument keys in a format string.

    Example::
        In [1]: find_argumentkeys_in_string('This is foo{foo} and {bar}')
        Out[1]: ['foo', 'bar']
    """
    exp = re.compile('\{(?P<argkey>' + ARGUMENT_KEY_RE_STR + ')\}')
    return exp.findall(string)


def value(arg, default=None):
    """
    Return the value of an Argument or create a new argument and immediately
    :meth:`Argument.retrieve_all()` it.
    :param arg: Either argument or string (to be used as key for creating a new Argument).
    :param default: Default value if no value could be retrieved.
    """
    if isinstance(arg, Argument):
        if not arg.is_empty:
            ret = arg.value
        else:
            ret = arg.retrieve_all().value
    else:
        assert isinstance(arg, str), 'Expected Argument or str, got `{0}`'.format(type(arg).__name__)
        ret = Argument(arg).retrieve_all(default=default).value
    return ret


def arg(arg, value=None):
    """
    Shortcut for creating an Argument with key = arg.

    :return: Argument(key)
    """
    return Argument(arg, value=value)