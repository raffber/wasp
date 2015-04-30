from uuid import uuid4 as generate_uuid
from . import ctx, Task
from .signature import FileSignature, CacheSignature, DummySignature
from .argument import ArgumentCollection, collection
from .util import is_iterable


class Node(object):
    def __init__(self, key=None, discard=False):
        if key is None:
            key = str(generate_uuid())
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
        self._path = path_(path)
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

    def __str__(self):
        return self.path


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

    @property
    def arguments(self):
        """
        Equivalent to self.read()
        """
        return self.read()

    def write(self, *args, **kw):
        """
        Creates an argument collection from *args and **kw using :meth:`arguments.collection`
        and writes it to the nodes storage.
        """
        col = collection(*args, **kw)
        if col.isempty():
            return
        if self.discard:
            self._cache = col
            return
        ctx.cache.prefix('symblic-nodes')[self.key] = col

    def update(self, *args, **kw):
        """
        Creates an argument collection from *args and **kw using :meth:`arguments.collection`
        and updates the argument collection of this node.
        """
        col = collection(*args, **kw)
        if col.isempty():
            return
        current = self.read()
        current.overwrite_merge(col)
        self.write(col)


def is_symbolic_node_string(arg):
    """
    Returns True if the argument string qualifies as a name
    for a :class:`SymbolicNode`.
    """
    assert isinstance(arg, str)
    return len(arg) > 1 and arg[0] == ':'


def nodes(*args):
    """
    Create a list of nodes based on nodes created for each arg in *args.
    If *args contains a :class:`wasp.task.Task`, all targets
    of this tasks are append to the return value. The following types
    of arguments are accepted::

        * Any subclass of Node is added as is
        * A Path object is converted into a :class:`wasp.node.FileNode(path)`
        * A string is converted to a :class:`wasp.node.SymbolicNode(path)` if it
            starts with a ':'. Otherwise it is converted into a :class:`wasp.node.FileNode(path)`

    :return: A list where is argument was processed as described above and added to the list.
    """
    ret = []
    for arg in args:
        if isinstance(arg, Task):
            ret.extend(arg.targets)
        if is_iterable(arg):
            ret.extend(nodes(arg))
        ret.append(node(arg))
    return ret


def node(arg=None):
    """
    Creates a node based on arg.
    The following types of arguments are accepted::

        * Any subclass of Node is returned as is
        * A Path object is converted into a :class:`wasp.node.FileNode(path)`
        * A string is converted to a :class:`wasp.node.SymbolicNode(path)` if it
            starts with a ':'. Otherwise it is converted into a :class:`wasp.node.FileNode(path)`
        * For a :class:`wasp.task.Task` object the first target node is returned.
    """
    from .fs import Path
    from .task import Task
    if arg is None:
        return SymbolicNode(discard=True)
    elif isinstance(arg, str):
        if is_symbolic_node_string(arg):
            return SymbolicNode(arg)
        else:
            return FileNode(arg)
    elif isinstance(arg, Path):
        return FileNode(arg.path)
    elif isinstance(arg, Node):
        return arg
    elif isinstance(arg, Task):
        if len(arg.targets) == 0:
            return None
        return arg.targets[0]
    raise TypeError('Invalid type passed to make_nodes, expected Node'
                    ', string, File or Task. Type was: {0}'.format(type(arg).__name__))
