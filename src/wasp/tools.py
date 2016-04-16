import sys
from .util import Proxy, load_module_by_name
from .fs import Directory

proxies = {}


class NoSuchToolError(RuntimeError):
    pass


class ToolsCollection(dict):

    def __init__(self, tooldir):
        super().__init__()
        if isinstance(tooldir, str):
            tooldir = Directory(tooldir)
        self._tooldir = tooldir

    def load(self, name, *args, path=None):
        from . import Directory
        if len(args) != 0:
            for arg in args:
                self.load(arg, path=path)
        if name in self:
            return
        if path is None:
            path = self._tooldir.path
        tooldir = Directory(path)
        try:
            sys.path.insert(0, tooldir.path)
            module = load_module_by_name(name)
            del sys.path[0]
        except FileNotFoundError:
            raise NoSuchToolError('Tool with name `{0}` not found in `{1}`'.format(name, path))
        self[name] = module
        if name in proxies.keys():
            # inject the tool proxy
            # TODO: why is it bugging any other way?!
            # specifically, proxy.__assign_object(asdf) does not
            # seem to work. The attriute name gets strangely converted
            # into _Context__assign_object... even if calling __getattribute__
            # directly
            p = proxies[name]
            data = object.__getattribute__(p, '_data')
            data['obj'] = module

    def __getitem__(self, item):
        if item not in self:
            self.load(item)
        return super().__getitem__(item)

    def get_tooldir(self):
        return self._tooldir

    def set_tooldir(self, tooldir):
        from .fs import Directory
        if isinstance(tooldir, str):
            tooldir = Directory(tooldir)
        assert isinstance(tooldir, Directory), 'tooldir must either be a path to a directory or a WaspDirectory'
        tooldir.ensure_exists()
        self._tooldir = tooldir

    tooldir = property(get_tooldir, set_tooldir)


def tool(name):
    from . import ctx
    assert isinstance(name, str), 'The name of the tool must be a name of a tool to be loaded.'
    try:
        return ctx.tools[name]
    except NoSuchToolError:
        pass
    proxy = Proxy()
    proxies[name] = proxy
    return proxy