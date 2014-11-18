from uuid import uuid4 as generate_uuid
import os
from . import ctx
from .signature import FileSignature, Signature
from .fs import File
from .arguments import ArgumentCollection

# TODO: is signature attribute actually required?!

class Node(object):
    def __init__(self, identifier=None):
        if identifier is None:
            identifier = generate_uuid()
        else:
            assert isinstance(identifier, str), 'Identifier for Node must be a string'
        self._id = identifier

    @property
    def signature(self):
        return Signature()

    def has_changed(self):
        raise NotImplementedError

    @property
    def identifier(self):
        return self._id


class FileNode(Node):
    def __init__(self, path):
        # TODO: optimize for performance => profile/benchmark
        if not os.path.isabs(path):
            path = os.path.realpath(path)
        self._path = path
        self._extension = os.path.splitext(path)[1]
        signature = ctx.signatures.get(self._path)
        if signature is None:
            # signature was either not initialized or it was invalidated
            signature = FileSignature(path=self._path)
            ctx.signatures.add(signature)
        super().__init__(path)

    @property
    def path(self):
        return self._path

    @property
    def extension(self):
        return self._extension

    def has_changed(self):
        sig = ctx.previous_signatures.get(self._path)
        if sig is None:
            return True
        if sig != self.signature:
            return True
        return False

    @property
    def signature(self):
        signature = ctx.signatures.get(self._path)
        assert signature is not None
        return signature


class SymbolicNode(Node):
    def __init__(self, identifier):
        super().__init__(identifier=identifier)

    def read(self):
        """
        Returns the content of the node in form of an ArgumentCollection.
        :return: An ArgumentCollection with the contents of the node.
        """
        arg_col = ctx.cache.prefix('symblic-nodes').get(self.identifier, None)
        assert isinstance(arg_col, ArgumentCollection), 'Cache: Invalid datastructure for symblic node storage.'
        return arg_col

    def write(self, args):
        """
        Write an ArgumentCollection and store it with the symbolic node.
        :param args: The ArgumentCollection to store
        :return: None
        """
        ctx.cache.prefix('symblic-nodes')[self.identifier] = args


def is_symbolic_node_string(arg):
    return len(arg) > 1 and arg[0] == ':'


def make_nodes(arg):
    lst = []
    if isinstance(arg, str):
        if is_symbolic_node_string(arg):
            lst = [SymbolicNode(arg)]
        else:
            lst = [FileNode(arg)]
    elif isinstance(arg, File):
        lst = [FileNode(arg.path)]
    elif isinstance(arg, Node):
        lst = [arg]
    elif isinstance(arg, list):
        for item in arg:
            lst.extend(make_nodes(item))
    else:
        raise TypeError('Invalid type passed to make_nodes, expected Node, string or list thereof.')
    return lst


def make_node(arg):
    ret = None
    if isinstance(arg, str):
        if is_symbolic_node_string(arg):
            return SymbolicNode(arg)
        else:
            return FileNode(arg)
    elif isinstance(arg, File):
        return FileNode(arg.path)
    elif isinstance(arg, Node):
        return arg
    raise TypeError('Invalid type passed to make_nodes, expected Node, string or list thereof.')


def remove_duplicates(nodes):
    d = {}
    ret = []
    for node in nodes:
        existing = d.get(node.identifier, None)
        if existing is None:
            d[node.identifier] = node
    for key, value in d.items():
        ret.append(value)
    return ret