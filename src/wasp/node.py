from uuid import uuid4 as generate_uuid
from . import ctx
from .signature import FileSignature, CacheSignature, DummySignature
from .argument import ArgumentCollection, collection


class Node(object):
    def __init__(self, key=None, discard=False):
        if key is None:
            key = generate_uuid()
        else:
            assert isinstance(key, str), 'Identifier for Node must be a string'
        self._key = key
        self._discard = discard

    @property
    def discard(self):
        return self._discard

    def _make_signature(self):
        raise NotImplementedError

    @property
    def key(self):
        return self._key

    def signature(self, ns=None):
        if self._discard:
            return DummySignature()
        signature = ctx.signatures.get(self.key, ns=ns)
        if signature is None:
            signature = self._make_signature()
            ctx.signatures.add(signature, ns=ns)
        return signature

    def has_changed(self, ns=None):
        sig = ctx.produced_signatures.get(self.key, ns=ns)
        if sig is None:
            return True
        if sig != self.signature(ns=ns):
            return True
        return False

    def invalidate(self, ns=None):
        ctx.signatures.invalidate_signature(self.key, ns=ns)

    def before_run(self, target=False):
        pass

    def after_run(self, target=False):
        pass


class FileNode(Node):
    def __init__(self, path):
        from .fs import path as path_
        self._path = path_(path
        )
        super().__init__(path)

    def _make_signature(self):
        return FileSignature(path=self.path)

    @property
    def path(self):
        return str(self._path)

    def to_file(self):
        return self._path

    def before_run(self, target=False):
        from .fs import File
        if target and isinstance(self._path, File):
            self._path.directory().create()


class SymbolicNode(Node):
    def __init__(self, key=None, discard=False):
        super().__init__(key=key, discard=discard)
        self._cache = None

    def _make_signature(self):
        return CacheSignature(self.key, prefix='symblic-nodes', cache_key=self.key)

    def read(self):
        """
        Returns the content of the node in form of an ArgumentCollection.
        :return: An ArgumentCollection with the contents of the node.
        """
        if self.discard:
            if self._cache is None:
                return ArgumentCollection()
            return self._cache
        arg_col = ctx.cache.prefix('symblic-nodes').get(self.key, None)
        if arg_col is None:
            return ArgumentCollection()
        assert isinstance(arg_col, ArgumentCollection), 'Cache: Invalid datastructure for symblic node storage.'
        return arg_col

    def write(self, *args, **kw):
        """
        Creates an argument collection from *args and **kw using :meth:`arguments.collection`.
        """
        col = collection(*args, **kw)
        if col.isempty():
            return
        if self.discard:
            self._cache = col
            return
        ctx.cache.prefix('symblic-nodes')[self.key] = col


def is_symbolic_node_string(arg):
    return len(arg) > 1 and arg[0] == ':'


def nodes(arg):
    if arg is None:
        return []
    from .task import Task
    lst = []
    if isinstance(arg, list) or isinstance(arg, tuple):
        for item in arg:
            lst.extend(nodes(item))
        return lst
    elif isinstance(arg, Task):
        return list(arg.targets)
    return [node(arg)]


def node(arg):
    from .fs import Path
    from .task import Task
    if isinstance(arg, str):
        if is_symbolic_node_string(arg):
            return SymbolicNode(arg)
        else:
            return FileNode(arg)
    elif isinstance(arg, Path):
        return FileNode(arg.path)
    elif isinstance(arg, Node):
        return arg
    elif isinstance(arg, Task):
        return arg.targets[0]
    raise TypeError('Invalid type passed to make_nodes, expected Node'
                    ', string, File or Task. Type was: {0}'.format(type(arg).__name__))


def remove_duplicates(nodes):
    d = {}
    ret = []
    for node in nodes:
        existing = d.get(node.key, None)
        if existing is None:
            d[node.key] = node
    for key, value in d.items():
        ret.append(value)
    return ret