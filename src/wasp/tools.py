from wasp import ctx

class ToolError(RuntimeError):
    pass

class NoSuchToolError(RuntimeError):
    pass

class inject_tool(object):
    def __init__(self, *args):
        for arg in args:
            assert isinstance(arg, str), 'inject_tool requires string arguments of tool names'
        self._args = args

    def __call__(self, f):
        def wrapper():
            tools = []
            for arg in self._args:
                tools.append(ctx.tool(arg))
            return f(*tools)
        return wrapper
