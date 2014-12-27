from .util import Serializable, checksum
from uuid import uuid4 as generate_uuid
from . import factory, ctx
from json import dumps
import os


class SignatureProvider(dict):

    def add(self, signature):
        self[signature.key] = signature

    def get(self, signature_identifier, *default):
        if len(default) > 1:
            raise TypeError('get expected at most 2 arguments, got {0}'.format(len(default)))
        return super().get(signature_identifier, *default)

    def save(self, cache):
        ret = {}
        for id_, signature in self.items():
            if signature.valid:
                ret[signature.key] = signature.to_json()
        cache.prefix('signaturedb').update(ret)

    def invalidate_signature(self, identifier):
        if isinstance(identifier, Signature):
            identifier = identifier.key
        assert isinstance(identifier, str), 'The identifier must be given as either a subclass of signature or str'
        signature = self.get(identifier)
        if signature is None:
            raise ValueError('Invalid identifier for signature')
        signature.refresh()


class SignatureStore(object):
    def __init__(self):
        # copy the dict, so that the cache can be written to
        self._signaturedb = {}

    def load(self, cache):
        self._signaturedb = dict(cache.prefix('signaturedb'))

    def get(self, id_):
        ret = self._signaturedb.get(id_)
        if ret is None:
            return Signature()
        return ret

    def update(self, id_, signature):
        self._signaturedb[id_] = signature


class Signature(Serializable):

    def __init__(self, value=None, valid=False, key=None):
        self._value = value
        self._valid = valid
        if key is not None:
            self._key = key
        else:
            self._key = generate_uuid()

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value

    @property
    def valid(self):
        return self._valid

    def invalidate(self):
        self._valid = False

    def __eq__(self, other):
        return not self.__ne__(other)

    def __ne__(self, other):
        return not other.valid or not self._valid or self._value != other.value

    def to_json(self):
        d = super().to_json()
        d.update({'value': self._value, 'valid': self.valid, 'identifier': self.key})
        return d

    @classmethod
    def from_json(cls, d):
        return cls(value=d['value'], valid=d['valid'], identifier=d['identifier'])

    def refresh(self, value=None):
        if value is not None:
            self._value = value
        return value


class FileSignature(Signature):
    def __init__(self, path, value=None, valid=True):
        assert path is not None, 'Path must be given for file signature'
        if not os.path.exists(path):
            valid = False
        self.path = path
        if value is None and valid:
            value = self.refresh()
        super().__init__(value, valid=valid, key=path)

    def to_json(self):
        d = super().to_json()
        d['path'] = self.path
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d['path'], value=d['value'], valid=d['valid'])

    def refresh(self, value=None):
        if value is not None:
            self._value = value
            self._valid = True
            return value
        if not os.path.exists(self.path):
            self._valid = False
            self._value = None
            return
        if os.path.isdir(self.path):
            # TODO: think about this.... maybe use all the content?!
            # that would be useful for example when packaging a .tgz
            self._value = 'directory'
            self._valid = True
            return self._value
        with open(self.path, 'rb') as f:
            data = f.read()
        value = checksum(data)
        self._value = value
        self._valid = True
        return value


factory.register(FileSignature)


class CacheSignature(Signature):
    def __init__(self, key, prefix=None, cache_key=None, value=None, valid=True):
        super().__init__(value, valid=valid, key=key)
        self._cache = ctx.cache.prefix(prefix)
        self._prefix = prefix
        self._cache_key = cache_key
        self.refresh(value)

    def to_json(self):
        d = super().to_json()
        d['prefix'] = self._prefix
        d['key'] = self._cache_key
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d['identifier'], key=d['key'], prefix=d['prefix'], value=d['value'], valid=d['valid'])

    def refresh(self, value=None):
        if value is not None:
            self._value = value
            return value
        data = self._cache.get(self._cache_key, None)
        if data is None:
            self._valid = False
            self._value = None
            return None
        # XXX: not very efficient, benchmark to see if optimization required
        jsonarr = factory.to_json(data)
        value = checksum(dumps(jsonarr))
        self._value = value
        return value


factory.register(CacheSignature)