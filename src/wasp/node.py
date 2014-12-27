from uuid import uuid4 as generate_uuid
import os
from . import ctx, signatures, old_signatures
from .signature import FileSignature, Signature, CacheSignature
from .argument import ArgumentCollection


class Node(object):
    def __init__(self, key=None):
        if key is None:
            key = generate_uuid()
        else:
            assert isinstance(key, str), 'Identifier for Node must be a string'
        self._key = key

    @property
    def key(self):
        return self._key

    @property
    def signature(self):
        signature = signatures.get(self.key)
        assert signature is not None
        return signature

    def has_changed(self):
        sig = old_signatures.get(self.key)
        if sig is None:
            return True
        if sig != self.signature:
            return True
        return False


class FileNode(Node):
    def __init__(self, path):
        # TODO: optimize for performance => profile/benchmark
        if not os.path.isabs(path):
            path = os.path.realpath(path)
        self._path = path
        self._extension = os.path.splitext(path)[1]
        signature = signatures.get(self._path)
        if signature is None:
            # signature was either not initialized or it was invalidated
            signature = FileSignature(path=self._path)
            signatures.add(signature)
        super().__init__(path)

    @property
    def path(self):
        return self._path

    def to_file(self):
        from .fs import File
        return File(self._path)

    @property
    def extension(self):
        return self._extension


class SymbolicNode(Node):
    def __init__(self, key):
        super().__init__(key=key)
        signature = signatures.get(self.key)
        if signature is None:
            # signature was either not initialized or it was invalidated
            signature = CacheSignature(key, prefix='symblic-nodes', cache_key=key)
            signatures.add(signature)

    def read(self):
        """
        Returns the content of the node in form of an ArgumentCollection.
        :return: An ArgumentCollection with the contents of the node.
        """
        arg_col = ctx.cache.prefix('symblic-nodes').get(self.key, None)
        assert isinstance(arg_col, ArgumentCollection), 'Cache: Invalid datastructure for symblic node storage.'
        return arg_col

    def write(self, args):
        """
        Write an ArgumentCollection and store it with the symbolic node.
        :param args: The ArgumentCollection to store
        :return: None
        """
        ctx.cache.prefix('symblic-nodes')[self.key] = args


def is_symbolic_node_string(arg):
    return len(arg) > 1 and arg[0] == ':'


def make_nodes(arg):
    if arg is None:
        return []
    from .task import Task
    lst = []
    if isinstance(arg, list) or isinstance(arg, tuple):
        for item in arg:
            lst.extend(make_nodes(item))
        return lst
    elif isinstance(arg, Task):
        return list(arg.targets)
    return [make_node(arg)]


def make_node(arg):
    from .fs import File
    from .task import Task
    if isinstance(arg, str):
        if is_symbolic_node_string(arg):
            return SymbolicNode(arg)
        else:
            return FileNode(arg)
    elif isinstance(arg, File):
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