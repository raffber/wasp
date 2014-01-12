import os
import sys
import imp
from subprocess import Popen, PIPE
import shlex
from threading import Event as ThreadingEvent


class Factory(object):
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
        stdout.write(output)
    if stderr is not None:
        stderr.write(err)
    return exit_code


module_cache = {}


def load_module_by_path(fpath):
    """
    Heavily inspired by waf's load_module
    """
    fpath = os.path.abspath(fpath)
    module = module_cache.get(fpath)
    if module is not None:
        return module
    module = imp.new_module('buildpy')
    dirname = os.path.dirname(fpath)
    sys.path.insert(0, dirname)
    with open(fpath, 'r') as f:
        code = f.read()
    comp = compile(code, fpath, 'exec')
    exec(comp, module.__dict__)
    sys.path.remove(dirname)
    module_cache[fpath] = module
    return module