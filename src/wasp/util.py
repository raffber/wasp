import threading
import os
import imp  # TODO: ...
import sys
from threading import Event as ThreadingEvent
from binascii import a2b_base64, b2a_base64
from string import Formatter
from uuid import uuid4 as uuid
import functools


def a2b(s):
    return a2b_base64(s)


def b2a(b):
    return b2a_base64(b)[:-1].decode('UTF-8')


class Factory(object):
    def __init__(self):
        self.d = {}

    def register(self, cls):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._collect_returns_fun = lambda ret: ret[-1] if len(ret) > 0 else None
        self._arg = None

    def collect(self, fun):
        self._collect_returns_fun = fun
        return self

    def __call__(self, *args, **kwargs):
        ret = []
        for callable_ in self:
            assert callable(callable_), 'Objects added to a CallableList must be callable'

            ret.append(callable_(*args, **kwargs))
        return self._collect_returns_fun(ret)


class Event(object):
    # TODO: possibly use asyncio module, once its clear
    # that it stays in the standard library
    # also, this would require python3.4 at minimum
    # one could also provide fallback options...
    def __init__(self, loop):
        self._funs = []
        self._loop = loop

    def connect(self, fun):
        self._funs.append(fun)
        return self

    def disconnect(self, fun):
        self._funs.remove(fun)

    def fire(self, *args, **kw):
        self._loop.fire_event(self, args, kw)

    def invoke(self, *args, **kw):
        for fun in self._funs:
            fun(*args, **kw)


class EventLoop(object):
    def __init__(self):
        self._threading_event = ThreadingEvent()
        self._events = []
        self._cancel = False

    def fire_event(self, evt, args, kw):
        self._events.append((evt, args, kw))
        self._threading_event.set()

    def cancel(self):
        self._cancel = True
        self._threading_event.set()

    def run(self):
        while True:
            self._threading_event.wait()
            self._threading_event.clear()
            if self._cancel:
                return
            for (evt, args, kw) in self._events:
                evt.invoke(*args, **kw)
            self._events.clear()
            # TODO: thread save this; lock on self._events
            # necessary? these things are atomic in python!
            # but is clear as well?


# XXX: this can still be improved a lot
# possibly use transparent object proxies to implement this.
class FunctionDecorator(object):
    def __init__(self, f):
        self._f = f
        functools.update_wrapper(self, f)

    def __call__(self, *args, **kwargs):
        return self._f(*args, **kwargs)


class ArgumentFunctionDecorator(object):

    def __call__(self, f):
        def wrapper(*args, **kw):
            return f(*args, **kw)
        functools.update_wrapper(wrapper, f)
        return wrapper


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
    """
    Heavily inspired by waf's load_module
    """
    fpath = os.path.realpath(fpath)
    # TODO: fpath to module name...
    # module = module_cache.get(fpath)
    # if module is not None:
    #     return module
    if module_name is None:
        module_name = str(uuid())
    module = imp.new_module(module_name)
    dirname = os.path.dirname(fpath)
    sys.path.insert(0, dirname)
    with open(fpath, 'r') as f:
        code = f.read()
    comp = compile(code, fpath, 'exec')
    module.__dict__['__file__'] = fpath
    exec(comp, module.__dict__)
    sys.path.remove(dirname)
    # module_cache[fpath] = module
    return module


def is_iterable(arg):
    # TODO: incorrect
    return isinstance(arg, list) or isinstance(arg, tuple)


class Proxy(object):
    __slots__ = ['_data', '__weakref__']

    def __init__(self, error_message, lock_thread=True):
        data = {}
        object.__setattr__(self, '_data', data)
        data['obj'] = object()
        assert isinstance(error_message, str)
        data['msg'] = error_message
        data['lock_thread'] = lock_thread
        if lock_thread:
            data['threadid'] = threading.current_thread().ident
        else:
            data['threadid'] = 0

    def __getattribute__(self, name):
        data = object.__getattribute__(self, '_data')
        if data['lock_thread'] and threading.current_thread().ident != data['threadid']:
            raise RuntimeError('Attempt to access proxy object from outside its scope.')
        if name == '__assign_object':
            def assign_object(obj):
                data['obj'] = obj
            return assign_object
        elif name == '__has_object':
            return data['obj'].__class__ != object
        if not data['obj'].__class__ != object:

            raise RuntimeError(data['msg'])
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
