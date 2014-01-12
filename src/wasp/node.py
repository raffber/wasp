from uuid import uuid4 as generate_uuid
from hashlib import md5
import os


class NodeDb(object):
    pass


class Signature(object):

    def __init__(self, value=-1, valid=False):
        self.value = value
        self._valid = valid

    @property
    def valid(self):
        return self._valid

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        return not other.valid or not self._valid or self.value != other.value

    def tojson(self):
        return {'value' : self.value, 'valid' : self.valid }


class FileSignature(object):

    def __init__(self, path):
        self.path = path
        m = md5()
        f = open(path, 'rb')
        m.update(f.read())
        f.close()
        super().__init__(m.digest(), valid=True)


class Node(object):
    def __init__(self, identifier=None):
        if identifier is None:
            identifier = generate_uuid()
        else:
            assert(isinstance(identifier, str), 'Identifier for Node must be a string')
        self._id = identifier

    @property
    def signature(self):
        return Signature()

    def has_changed(self, oldsignature):
        return self.signature != oldsignature

    @property
    def identifier(self):
        return self._id


class FileNode(object):
    def __init__(self, path):
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        self._path = path
        self._extension = os.path.splitext(path)[1]
        self._signature_cache = None
        super().__init__(path)

    @property
    def path(self):
        return self._path

    @property
    def extension(self):
        return self._extension

    @property
    def signature(self):
        if self._signature_cache is None:
            self._signature_cache = FileSignature(path)
        return self._signature_cache


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

def remove_duplicates(lst):
    pass