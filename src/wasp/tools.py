from .util import Proxy
from . import ctx

proxies = {}


class ToolError(RuntimeError):
    pass


class NoSuchToolError(RuntimeError):
    pass


def tool(name):
    assert isinstance(name, str), 'The name of the tool must be a name of a tool to be loaded.'
    if ctx.__has_object:
        try:
            return ctx.tools(name)
        except ToolError:
            pass
    proxy = Proxy("Tools can only be accessed after they have been loaded.")
    proxies[name] = proxy
    return proxy