from uuid import uuid4 as generate_uuid
import os
from . import ctx
from .signature import FileSignature, Signature


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


def make_nodes(lst_or_string):
    lst = []
    if isinstance(lst_or_string, str):
        lst = [FileNode(lst_or_string)]
    elif isinstance(lst_or_string, Node):
        lst = [lst_or_string]
    elif isinstance(lst_or_string, list):
        for item in lst_or_string:
            lst.extend(make_nodes(item))
    else:
        raise TypeError('Invalid type passed to make_nodes, expected Node, string or list thereof.')
    return lst


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