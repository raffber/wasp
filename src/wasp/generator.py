from .node import FileNode
from .decorators import decorators


class TaskGenerator(object):
    def __init__(self):
        pass

    def handles(self, node):
        raise NotImplementedError

    def generate(self, nodes, **kw):
        raise NotImplementedError


class FileDecoratorGenerator(object):
    def __init__(self, extensions, fun):
        super().__init__()
        if isinstance(extensions, str):
            extensions = [extensions]
        assert isinstance(extensions, list), 'File extensions for generator decorator must '\
                                             'either be given as list of string or string'
        self._extensions = extensions
        self._fun = fun

    def handles(self, node):
        if isinstance(node, FileNode):
            if node.extension in self._extensions:
                return True
        return False

    def generate(self, nodes, **kw):
        return self._fun(nodes, **kw)


class generate(object):
    def __init__(self, extensions):
        self._extension = extensions

    def __call__(self, f):
        decorators.generators.append(FileDecoratorGenerator(self._extensions, f))
        return f