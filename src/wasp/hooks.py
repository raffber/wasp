from .decorators import decorators


class Hooks(object):
    def __init__(self):
        self._init = []

    @property
    def init(self):
        return self._init

    def run_init(self):
        for f in self._init:
            f()


class init(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.init.append(f)
        return f


class create_context(object):
    def __init__(self):
        pass

    def __call__(self, f):
        decorators.create_context = f
        return f
