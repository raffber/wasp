from uuid import uuid4 as generate_uuid

from .signature import FileSignature, CacheSignature, UnchangedSignature
from .argument import ArgumentCollection, collection
from .util import is_iterable


class Node(object):
    """
    Abstract node class. A node is an entity which is either produced
    (he node is a **target** of the task) or consumed by
    a task (the node is a **source** of the task). Thus, a task maps
    **source** nodes to **target** nodes.

    A node points to information (such as a file on the filesystem) and
    keeps track of changes that may happen to this information by means
    of a :class:`wasp.signature.Signature`. Thus, based on the signatures
    of the nodes, it can be determined if a task needs to executed or if
    its sources or targets have not changed since the last run.

    A node must contain a key, which ideally also serves as an
    identifier to the information the node points to (e.g. a file path).
    Multiple nodes may be created with the same key. If so, these objects
    must behave exactly the same.

    :param key: The key of the node. Expects ``str`` or ``None``. If ``None`` is
        given, a key based on a uuid is generated.
    """
    def __init__(self, key=None):
        if key is None:
            key = str(generate_uuid())
        else:
            assert isinstance(key, str), 'Identifier for Node must be a string'
        self._key = key

    def _make_signature(self):
        """
        Must be overwritten by child classes. Should return an object
        of type :class:`wasp.signature.Signature` which belongs to this
        node.
        """
        raise NotImplementedError

    @property
    def key(self):
        """
        Returns a key describing this node.
        """
        return self._key

    @property
    def name(self):
        return self._key

    def signature(self, ns=None):
        """
        Returns a :class:`wasp.signature.Signature` object which
        defines the last seen version of the information this node
        points to (within the given namespace). For more information
        on namespaces see :class:`wasp.signature.Signature`.

        :param ns: The namespace for which the signature should be returned.
        """
        from . import ctx
        signature = ctx.signatures.get(self.key, ns=ns)
        if signature is None:
            signature = self._make_signature()
            ctx.signatures.add(signature, ns=ns)
        return signature

    def has_changed(self, ns=None):
        """
        Returns True if the node has changed within the given namespace.
        For more information on namespaces see :class:`wasp.signature.Signature`.
        """
        from . import ctx
        sig = ctx.produced_signatures.get(self.key, ns=ns)
        if sig is None:
            return True
        cur_sig = self.signature(ns=ns)
        if not cur_sig.valid:
            cur_sig.refresh()
        if sig != cur_sig:
            return True
        return False

    def invalidate(self, ns=None):
        """
        Invalidates the signature of this node. Thus, it must be reloaded
        the next time its value is queried.

        :param ns: he namespace for which the signature should be invalidated.
        """
        from . import ctx
        ctx.signatures.invalidate_signature(self.key, ns=ns)

    def before_run(self, target=False):
        """
        Called before a task is run either consuming this node (target == False)
        or producing this node (target == True).
        """
        pass

    def after_run(self, target=False):
        """
        Called after a task is run either consuming this node (target == False)
        or producing this node (target == True).
        """
        pass


class FileNode(Node):
    """
    A node which points to a file in the filesystem.

    :param path: Path of the file which the node points to.
    """
    def __init__(self, path):
        from .fs import path as path_
        self._path = path_(path)
        # sanitize path name s.t. we get consistent
        # path separators and stuff
        super().__init__(str(self._path))

    def _make_signature(self):
        return FileSignature(path=self.path)

    @property
    def path(self):
        """
        Return the filesystem path of the node.
        """
        return str(self._path)

    def to_file(self):
        """
        Return a :class:`wasp.fs.Path` object with the
        path pointed to by this node.
        """
        return self._path

    def before_run(self, target=False):
        from .fs import File
        if target and isinstance(self._path, File):
            self._path.directory().create()

    def __str__(self):
        """
        Equivalent to ``node.path``.
        """
        return self.path


class SymbolicNode(Node):
    """
    A SymbolicNode points to a location in the cache of wasp and
    may be used to pass information between tasks, such as the location
    of a compiler or information on how to run a task.
    It can also be used to store information between runs.
    SymbolicNodes have names which start with a colon (':') and can be
    created using the :func:`wasp.node.node` function::

        n = node(':cpp/compiler')

    :param key: The name of the node.
    """
    def __init__(self, key=None):
        from . import ctx
        if key is None:
            key = ctx.generate_name()
        super().__init__(key=key)

    def _make_signature(self):
        return CacheSignature(self.key, prefix='symblic-nodes', cache_key=self.key)

    def read(self):
        """
        Returns the content of the node in form of an ArgumentCollection.
        """
        from . import ctx
        arg_col = ctx.cache.prefix('symblic-nodes').get(self.key, None)
        if arg_col is None:
            return ArgumentCollection()
        if isinstance(arg_col, dict):
            arg_col = ArgumentCollection.from_dict(arg_col)
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
        from . import ctx
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

    def __str__(self):
        return self.key


class SpawningNode(SymbolicNode):
    def __init__(self, key=None):
        super().__init__(key=key)
        self._spawn = None

    @property
    def spawn(self):
        return self._spawn

    @spawn.setter
    def spawn(self, value):
        assert callable(value) or value is None
        self._spawn = value

    def do_spawn(self):
        if self._spawn is None:
            return []
        ret = self._spawn()
        if not is_iterable(ret):
            return [ret]
        return list(ret)


def spawn(key, spawn=None):
    ret = SpawningNode(key)
    ret.spawn = spawn
    return ret


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
        * For a :class:`wasp.task.Task` or :class:`wasp.task.TaskGroup` object the
            target nodes are added.

    :return: A list where is argument was processed as described above and added to the list.
    """
    from . import Task, TaskGroup
    ret = []
    for arg in args:
        if arg is None:
            continue
        elif isinstance(arg, Task) or isinstance(arg, TaskGroup):
            ret.extend(arg.targets)
        elif is_iterable(arg):
            ret.extend(nodes(*arg))
        else:
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
    from .task import Task, TaskGroup
    if arg is None:
        return SymbolicNode()
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
    elif isinstance(arg, TaskGroup):
        if len(arg.targets) == 0:
            return None
        return arg.targets[0]
    raise TypeError('Invalid type passed to node, expected Node'
                    ', string, File or Task. Type was: {0}'.format(type(arg).__name__))
