from .util import Proxy


proxies = {}


class ToolError(RuntimeError):
    pass


class NoSuchToolError(RuntimeError):
    pass


class ToolProxy(Proxy):

    def __init__(self, name):
        assert isinstance(name, str), 'The name of the tool must be a name of a tool to be loaded.'
        proxies[name] = self