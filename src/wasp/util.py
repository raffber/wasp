import os
import sys
import imp
from subprocess import Popen, PIPE
import shlex
from threading import Event as ThreadingEvent
from binascii import a2b_base64, b2a_base64
from string import Formatter
from uuid import uuid4 as uuid


def a2b(s):
    return a2b_base64(s)


def b2a(b):
    return b2a_base64(b)[:-1].decode('UTF-8')


class Factory(object):
    # TODO: add checks and require subtype of base
    def __init__(self, base):
        self._base = base
        self.d = {}

    @property
    def base(self):
        return self._base

    def register(self, cls, name=None):
        if name is None:
            name = cls.__name__
        self.d[name] = cls

    def getclass(self, name):
        return self.d.get(name, None)

    def create(self, name, *args, **kw):
        cls = self.getclass(name)
        if cls is None:
            return None
        return cls(*args, **kw)


class Event(object):
    def __init__(self, loop):
        self._funs = []
        self._loop = loop

    def connect(self, fun):
        self._funs.append(fun)

    def disconnect(self, fun):
        self._funs.remve(fun)

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
                # TODO: thread save???


def run_command(cmd, stdout=None, stderr=None, timeout=100):
    cmd = shlex.split(cmd)
    process = Popen(cmd, stdout=PIPE, stderr=PIPE)
    output, err = process.communicate()
    exit_code = process.wait(timeout=timeout)
    if stdout is not None:
        stdout.write(output.decode('UTF-8'))
    if stderr is not None:
        stderr.write(err.decode('UTF-8'))
    return exit_code


module_cache = {}


class UnusedArgFormatter(Formatter):
    def check_unused_args(self, used_args, args, kwargs):
        pass

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            return args[key]
        if isinstance(key, str):
            return kwargs.get(key, '')


def load_module_by_path(fpath):
    """
    Heavily inspired by waf's load_module
    """
    fpath = os.path.abspath(fpath)
    module = module_cache.get(fpath)
    if module is not None:
        return module
    module = imp.new_module(str(uuid()))
    dirname = os.path.dirname(fpath)
    sys.path.insert(0, dirname)
    with open(fpath, 'r') as f:
        code = f.read()
    comp = compile(code, fpath, 'exec')
    exec(comp, module.__dict__)
    sys.path.remove(dirname)
    module_cache[fpath] = module
    return module


class Proxy(object):
    __slots__ = ["_obj", "__weakref__"]

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)

    #
    # proxying (special cases)
    #
    def __getattribute__(self, name):
        return getattr(object.__getattribute__(self, "_obj"), name)

    def __delattr__(self, name):
        delattr(object.__getattribute__(self, "_obj"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_obj"), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_obj"))

    def __str__(self):
        return str(object.__getattribute__(self, "_obj"))

    def __repr__(self):
        return repr(object.__getattribute__(self, "_obj"))

    #
    # factories
    #
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        def make_method(name):
            def method(self, *args, **kw):
                return getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw)
            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins