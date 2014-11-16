from .util import Factory
from uuid import uuid4 as generate_uuid
from .util import Factory, b2a
from hashlib import md5
from . import register
import os


class SignatureProvider(object):
    def __init__(self):
        self._db = {}

    def add(self, signature):
        self._db[signature.identifier] = signature

    def get(self, signature_identifier):
        return self._db.get(signature_identifier)

    def save(self, cache):
        ret = {}
        for id_, signature in self._db.items():
            if signature.valid:
                ret[signature.identifier] = signature.to_json()
        cache.prefix('signaturedb').update(ret)

    def invalidate_signature(self, identifier):
        if isinstance(identifier, Signature):
            identifier = identifier.identifier
        assert isinstance(identifier, str), 'The identifier must be given as either a subclass of signature or str'
        signature = self._db.get(identifier)
        if signature is None:
            raise ValueError('Invalid identifier for signature')
        signature.refresh()


class SignatureStore(object):
    def __init__(self, cache):
        # copy the dict, so that the cache can be written to
        self._signaturedb = dict(cache.prefix('signaturedb'))

    def get(self, id_):
        raise NotImplementedError
        # TODO: automatically casted to signature
        # d = self._signaturedb.get(id_)
        # if d is None:
        #     return Signature()
        # return signature_factory.create(d['type'], **d)


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

    @classmethod
    def from_json(cls, d):
        return cls(value=d['value'], valid=d['valid'], identifier=d['identifier'])

    def refresh(self):
        pass

@register
class FileSignature(Signature):
    def __init__(self, path=None, value=None, valid=True):
        assert path is not None, 'Path must be given for file signature'
        if not os.path.exists(path):
            valid = False
        self.path = path
        if value is None and valid:
            value = self.refresh()
        super().__init__(value, valid=valid, identifier=path)

    def to_json(self):
        d = super().to_json()
        d['path'] = self.path
        d['type'] = self.__class__.__name__
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d['path'], value=d['value'], valid=d['valid'])

    def refresh(self):
        m = md5()
        f = open(self.path, 'rb')
        m.update(f.read())
        f.close()
        value = b2a(m.digest())
        self.value = value
        return value
