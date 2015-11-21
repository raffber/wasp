"""
Arguments represent the primary tool for passing data between tasks.
They main class :class:`Argument` is a serializable key-value pair.
"""

from . import ctx, factory
import re
import json
from .util import Serializable, UnusedArgFormatter, parse_assert, is_json_primitive, is_json_serializable


ARGUMENT_KEY_RE_STR = '[\w\d]+[\w\d_-]*'
"""A key of an argument must match this string"""
ARGUMENT_KEY_RE = re.compile('^' + ARGUMENT_KEY_RE_STR + '$')
"""Compiled version of :data:`wasp.argument.ARGUMENT_KEY_RE`"""


class MissingArgumentError(Exception):
    """
    Raised when an argument is expected to be present, but is missing.
    """
    pass


class ArgumentCollection(dict):

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
                assert is_json_serializable(v), 'Values must be json serializable such that' \
                                                'they can be assigned to an Argument'
                ret.add(Argument(k).assign(v))
            else:
                ret.add(v)
        return ret

    def value(self, key, default=None):
        """
        Returns the value of the argument associated with ``key``. If ``key`` is not in self,
        returns ``default``
        """
        arg = self.get(key)
        if arg is None:
            return default
        return arg.value

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
        if is_json_serializable(value) and not isinstance(value, Argument):
            value = Argument(key, value=value)
        assert isinstance(value, Argument), 'Can only set Argument in ArgumentCollection.__setitem__.'
        super().__setitem__(key, value)

    def isempty(self):
        """
        Returns True if self has contains no items, False otherwise.
        """
        return len(self) == 0

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
            except ValueError:
                raise ValueError('Invalid json file `{0}`'.format(fpath))
        self = cls()
        parse_assert(isinstance(d, dict), 'json file for ArgumentCollection must start with at dictionary.')
        for k, v in d.items():
            self.add(Argument(k).assign(v))
        return self

    def __repr__(self):
        return '{' + ', '.join('{0} = {1}'.format(k, v.value) for k, v in self.items()) + '}'


def collection(*args, **kw):
    """
    Creates an ArgumentCollection from args and kw.
    :param args: Accepts list, dict ArgumentCollection or Argument
    :param kw: Calls ArgumentCollection.from_dict.
    :return: An ArgumentCollection created from the arguments
    """
    col = ArgumentCollection()
    for arg in args:
        if isinstance(arg, list):
            col.overwrite_merge(collection(arg))
        elif isinstance(arg, ArgumentCollection):
            col.overwrite_merge(arg)
        elif isinstance(arg, dict):
            col.overwrite_merge(ArgumentCollection.from_dict(arg))
        elif isinstance(arg, Argument):
            col.add(arg)
    col.overwrite_merge(ArgumentCollection.from_dict(kw))
    return col


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
            self._value = (self._required_type)(value)
            if not isinstance(value, self._required_type):
                raise TypeError('Argument {0} must be of type {1}, but found type {2}!'.format(
                    self.key, self._required_type.__name__, type(value).__name__))
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
        from .option import OptionsCollection

        if isinstance(arg, Environment):
            # environment variable
            return arg.get(self.key.upper())
        elif isinstance(arg, OptionsCollection):
            option = arg.all().get(self.key.lower(), None)
            if option:
                return option.value
        elif isinstance(arg, ArgumentCollection):
            v = arg.get(self.key)
            if v is not None:
                return v.value
        elif isinstance(arg, dict):
            # keyword argument
            return arg.get(self.key, None)
        elif isinstance(arg, Metadata):
            return arg.get(self.key)
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