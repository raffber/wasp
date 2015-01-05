import importlib
import threading
import os
from importlib.machinery import SourceFileLoader
from threading import Event as ThreadingEvent
from binascii import a2b_base64, b2a_base64
from string import Formatter
from uuid import uuid4 as uuid
from zlib import adler32
import functools


def a2b(s):
    return a2b_base64(s)


def b2a(b):
    return b2a_base64(b)[:-1].decode('UTF-8')


def checksum(data):
    return '{0}'.format(adler32(data) & 0xffffffff)


def json_checksum(data):
    ret = 0
    if isinstance(data, dict):
        for k, v in data.items():
            ret += json_checksum(v)*json_checksum(k)
    elif isinstance(data, list):
        for item in data:
            ret += json_checksum(item)
    else:
        ret = adler32('{0}'.format(data).encode('ASCII')) & 0xffffffff
    return ret


class Factory(object):
    def __init__(self):
        self.d = {}

    def register(self, cls):
        if not issubclass(cls, Serializable):
            raise ValueError('Expected a subclass of Serializable.')
        self.d[cls.__name__] = cls

    def getclass(self, typename):
        return self.d.get(typename, None)

    def create(self, d):
        typename = d['__type__']
        cls = self.getclass(typename)
        if cls is None:
            raise ValueError('No such type registered: {0}'.format(typename))
        return cls.from_json(d)

    def from_json(self, d):
        if isinstance(d, dict) and '__type__' in d.keys():
            value = self.create(d)
        elif isinstance(d, list):
            value = [self.from_json(v) for v in d]
        elif isinstance(d, dict):
            value = {}
            for k, v in d.items():
                value[k] = self.from_json(v)
        else:  # primitives
            value = d
        return value

    def to_json(self, arg):
        ret = None
        if isinstance(arg, Serializable):
            ret = arg.to_json()
        elif isinstance(arg, dict):  # recurse
            ret = {}
            for k, v in arg.items():
                ret[k] = self.to_json(v)
        elif isinstance(arg, list):  # recurse
            ret = [self.to_json(v) for v in arg]
        else:  # primitives
            ret = arg
        return ret


class Serializable(object):

    def to_json(self):
        return {'__type__': self.__class__.__name__}

    @classmethod
    def from_json(cls, d):
        raise NotImplementedError


class CannotSerializeError(Exception):
    pass


class CallableList(list):

    def __init__(self, arg=None):
        super().__init__()
        self._collect_returns_fun = lambda ret: ret[-1] if len(ret) > 0 else None
        self._arg = arg

    def collect(self, fun):
        self._collect_returns_fun = fun
        return self

    def __call__(self, *args, **kwargs):
        ret = []
        for callable_ in self:
            assert callable(callable_), 'Objects added to a CallableList must be callable'
            if self._arg is not None:
                ret.append(callable_(self._arg, *args, **kwargs))
            else:
                ret.append(callable_(*args, **kwargs))
        return self._collect_returns_fun(ret)


class Event(object):
    # TODO: possibly use asyncio module, once its clear
    # that it stays in the standard library
    # also, this would require python3.4 at minimum
    # one could also provide fallback options...
    def __init__(self, loop=None):
        self._funs = []
        self._loop = loop

    def connect(self, fun):
        self._funs.append(fun)
        return self

    def disconnect(self, fun):
        self._funs.remove(fun)

    def fire(self, *args, **kw):
        if self._loop is None:
            self.invoke(*args, **kw)
        else:
            self._loop.fire_event(self, args, kw)

    def invoke(self, *args, **kw):
        for fun in self._funs:
            fun(*args, **kw)


class EventLoop(object):
    def __init__(self, interrupted=None):
        self._threading_event = ThreadingEvent()
        self._events = []
        self._cancel = False
        self._interrupted = interrupted
        self._running = False
        self._started = False
        self._start_id = None

    def fire_event(self, evt, args, kw):
        self._events.append((evt, args, kw))
        self._threading_event.set()

    def cancel(self):
        self._cancel = True
        self._threading_event.set()

    @property
    def running(self):
        return self._running

    @property
    def started(self):
        return self._started

    def run(self):
        self._start_id = threading.current_thread().ident
        self._started = True
        self._running = True
        try:
            while True:
                self._threading_event.wait()
                self._threading_event.clear()
                if self._cancel:
                    break
                for (evt, args, kw) in self._events:
                    evt.invoke(*args, **kw)
                self._events.clear()
                # TODO: thread save this; lock on self._events
                # necessary? these things are atomic in python!
                # but is clear as well?
        except KeyboardInterrupt:
            self._running = False
            if self._interrupted is not None:
                self._interrupted()
            return False
        finally:
            self._start_id = None
        self._running = False
        return True


def lock(f):
    class LockWrapper(object):
        def __init__(self, f):
            self._f = f

        def __get__(self, instance, owner):
            if instance is None:
                raise TypeError('Function `{0}` cannot be used as class '
                                'method with an @lock decorator.'.format(self._f.__name__))
            if not hasattr(instance, '__lock__'):
                object.__setattr__(instance, '__lock__', threading.Lock())

            @functools.wraps(self._f)
            def wrapper(*args, **kw):
                with instance.__lock__:
                    return f(instance, *args, **kw)
            return wrapper
    return LockWrapper(f)


# XXX: this can still be improved a lot
# possibly use transparent object proxies to implement this.
class FunctionDecorator(object):
    def __init__(self, f):
        self._f = f
        functools.update_wrapper(self, f)

    def __call__(self, *args, **kwargs):
        return self._f(*args, **kwargs)


class UnusedArgFormatter(Formatter):
    def check_unused_args(self, used_args, args, kwargs):
        pass

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            return args[key]
        if isinstance(key, str):
            return kwargs.get(key, '')


def parse_assert(condition, msg):
    if not condition:
        raise ValueError(msg)


def load_module_by_path(fpath, module_name=None):
    if module_name is None:
        module_name = str(uuid())
    fpath = os.path.realpath(fpath)
    if os.path.isdir(fpath):
        fpath = os.path.join(fpath, '__init__.py')
    loader = SourceFileLoader(module_name, fpath)
    m = loader.load_module()
    return m


def load_module_by_name(name):
    return importlib.import_module(name)


def is_iterable(arg):
    # TODO: incorrect
    return isinstance(arg, list) or isinstance(arg, tuple) or isinstance(arg, set)


def is_json_primitive(arg):
    return isinstance(arg, float) or isinstance(arg, bool) or isinstance(arg, str) or isinstance(arg, int)


class Namespace(object):

    def __getattr__(self, item):
        return object.__getattribute__(self, item)

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)


class Proxy(object):
    __slots__ = ['_data', '__weakref__']

    def __init__(self):
        data = {}
        object.__setattr__(self, '_data', data)
        data['obj'] = object()

    def __getattribute__(self, name):
        data = object.__getattribute__(self, '_data')
        if name == '__assign_object':
            def assign_object(obj):
                data['obj'] = obj
            return assign_object
        elif name == '__has_object':
            return data['obj'].__class__ != object
        if not data['obj'].__class__ != object:
            return object.__getattribute__(self, name)
        return getattr(data['obj'], name)

    def __delattr__(self, name):
        data = object.__getattribute__(self, '_data')
        delattr(data['obj'], name)

    def __setattr__(self, name, value):
        data = object.__getattribute__(self, '_data')
        setattr(data['obj'], name, value)

    def __nonzero__(self):
        data = object.__getattribute__(self, '_data')
        return bool(data['obj'])

    def __str__(self):
        data = object.__getattribute__(self, '_data')
        return str(data['obj'])

    def __repr__(self):
        data = object.__getattribute__(self, '_data')
        return repr(data['obj'])
