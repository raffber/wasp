from .util import Serializable, checksum, json_checksum, lock
from uuid import uuid4 as generate_uuid
from . import factory, ctx
import os


def _get_ns(ns):
    if ns is None:
        return ctx.current_namespace or 'default'
    return ns


class SignatureProvider(object):
    """
    Storage class for :class:`Signature` objects, which stores
    the current values of the signatures.
    """

    def __init__(self):
        self._d = {}

    @lock
    def add(self, signature, ns=None):
        """
        Adds a :class:`Signature` object to the storage.
        """
        ns = _get_ns(ns)
        if ns not in self._d:
            self._d[ns] = {}
        self._d[ns][signature.key] = signature

    @lock
    def get(self, key, default=None, ns=None):
        """
        Returns a :class:`Signature` object based on ``key`` or ``default`` if the
        signature was not found.

        :param key: Key of the :class:`Signature`.
        :param default: Default value if the :class:`Signature` was not found.
        :param ns: The namespace where the search should be conducted.
        :return: :class:`Signature` object or ``default``.
        """
        ns = _get_ns(ns)
        if ns not in self._d:
            self._d[ns] = {}
        return self._d[ns].get(key, *default)

    def save(self, cache):
        """
        Saves this object to ``cache``.
        """
        cache.prefix('signaturedb').update(self._d)

    @lock
    def invalidate_signature(self, key, ns=None):
        """
        Invalidates a signature with ``key`` in the given namespace ``ns``.
        The signature will be refreshed automatically when its value is
        queried next.
        """
        ns = _get_ns(ns)
        if isinstance(key, Signature):
            key = key.key
        assert isinstance(key, str), 'The key must be given as either a subclass of signature or str'
        if ns not in self._d:
            self._d[ns] = {}
        signature = self._d[ns].get(key)
        if signature is None:
            raise ValueError('Invalid key for signature')
        signature.invalidate()

    @lock
    def invalidate_all(self):
        """
        Invalidates all signatures in all namespaces.
        """
        for nsv in self._d.values():
            for sig in nsv.values():
                sig.invalidate()


class ProducedSignatures(object):
    """
    Storage object which provides access to signatures that
    were already produced by some task.
    """
    def __init__(self):
        self._signaturedb = {}

    def load(self, cache):
        """
        Loads the object from the ``cache``.
        """
        # copy the dict, so that the cache can be written to
        self._signaturedb = dict(cache.prefix('signaturedb'))

    def clear(self):
        """
        Clears all signatures of this object.
        """
        self._signaturedb.clear()

    @lock
    def get(self, key, ns=None):
        """
        Returns a :class:`Signature` object based on ``key``. If
        ``key`` does not exist in self, an empty signature is returned.
        """
        ns = _get_ns(ns)
        if ns not in self._signaturedb:
            self._signaturedb[ns] = {}
        ret = self._signaturedb[ns].get(key)
        if ret is None:
            return Signature()
        return ret

    @lock
    def update(self, signature, ns=None):
        """
        Updates the signature with the new signature.
        """
        ns = _get_ns(ns)
        if ns not in self._signaturedb:
            self._signaturedb[ns] = {}
        self._signaturedb[ns][signature.key] = signature


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
        d.update({'value': self._value, 'valid': self.valid, 'key': self.key})
        return d

    @classmethod
    def from_json(cls, d):
        return cls(value=d['value'], valid=d['valid'], key=d['key'])

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

    @lock
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
            # raise RuntimeError('FileSignature cannot be a directory')
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
        self._cache = None
        self._prefix = prefix
        self._cache_key = cache_key
        self.refresh(value)

    def to_json(self):
        d = super().to_json()
        d['prefix'] = self._prefix
        d['cache_key'] = self._cache_key
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d['key'], cache_key=d['key'], prefix=d['prefix'], value=d['value'], valid=d['valid'])

    @lock
    def refresh(self, value=None):
        if value is not None:
            self._value = value
            return value
        if self._cache is None:
            self._cache = ctx.cache.prefix(self._prefix)
        data = self._cache.get(self._cache_key, None)
        if data is None:
            self._valid = False
            self._value = None
            return None
        jsonarr = factory.to_json(data)
        value = str(json_checksum(jsonarr))
        self._value = value
        if self.key != ':dc':
            return value
        return value


factory.register(CacheSignature)


class DummySignature(Signature):

    def to_json(self):
        return None

    @classmethod
    def from_json(cls, d):
        return cls()

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


factory.register(DummySignature)