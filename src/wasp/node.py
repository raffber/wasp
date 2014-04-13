from uuid import uuid4 as generate_uuid
from hashlib import md5
import os
from .util import Factory, b2a
from . import ctx


class SignatureDb(object):
    def __init__(self, cache):
        self._cache = cache
        self._db = {}

    def add(self, signature):
        self._db[signature.identifier] = signature

    def get(self, signature_identifier):
        return self._db.get(signature_identifier)

    def save(self):
        ret = {}
        for id_, signature in self._db.items():
            if signature.valid:
                ret[signature.identifier] = signature.to_json()
        self._cache.setcache('signaturedb', ret)


class PreviousSignatureDb(object):
    def __init__(self, cache):
        # copy the dict, so that the cache can be written to
        self._signaturedb = dict(cache.getcache('signaturedb'))

    def get(self, id_):
        d = self._signaturedb.get(id_)
        if d is None:
            return Signature()
        return signature_factory.create(d['type'], **d)


class Signature(object):

    def __init__(self, value=None, valid=False, identifier=None):
        self.value = value
        self._valid = valid
        if identifier is not None:
            self._id = identifier
        else:
            self._id = generate_uuid()

    @property
    def identifier(self):
        return self._id

    @property
    def valid(self):
        return self._valid

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        return not other.valid or not self._valid or self.value != other.value

    def to_json(self):
        return {'value': self.value, 'valid': self.valid,
                'type': self.__class__.__name__, 'identifier': self.identifier}


class FileSignature(Signature):
    def __init__(self, path=None, value=None, valid=True, **kw):
        assert path is not None, 'Path must be given for file signature'
        if not os.path.exists(path):
            valid = False
        self.path = path
        if value is None and valid:
            m = md5()
            f = open(path, 'rb')
            m.update(f.read())
            f.close()
            value = b2a(m.digest())
        super().__init__(value, valid=valid, identifier=path)

    def to_json(self):
        d = super().to_json()
        d['path'] = self.path
        d['type'] = self.__class__.__name__
        return d


signature_factory = Factory(Signature)
signature_factory.register(Signature)
signature_factory.register(FileSignature)


class Node(object):
    def __init__(self, identifier=None):
        if identifier is None:
            identifier = generate_uuid()
        else:
            assert isinstance(identifier, str), 'Identifier for Node must be a string'
        self._id = identifier
        # make sure that signature is created and or added to db
        # this enables signatures to lazily generate their signatures
        # which improves performance
        self.signature

    @property
    def signature(self):
        return Signature()

    def has_changed(self):
        raise NotImplementedError

    @property
    def identifier(self):
        return self._id


class FileNode(Node):
    def __init__(self, path, signature=None):
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        self._path = path
        self._extension = os.path.splitext(path)[1]
        if signature is not None:
            self._signature_cache = signature
        else:
            self._signature_cache = None
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
        if self._signature_cache is None:
            sig = ctx.signatures.get(self._path)
            if sig is None:
                self._signature_cache = FileSignature(path=self._path)
                ctx.signatures.add(self._signature_cache)
            else:
                self._signature_cache = sig
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