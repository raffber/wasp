from .decorators import decorators


class init(object):
    def __init__(self, f):
        decorators.init.append(f)


class create_context(object):
    def __init__(self, f):
        decorators.create_context = f
        self.f = f
