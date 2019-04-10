from .util import Serializable, checksum, json_checksum, lock
from uuid import uuid4 as generate_uuid
from . import factory
import os


def _get_ns(ns):
    if ns is None:
        from wasp import ctx
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

    def get_signatures(self, ns=None):
        ns = _get_ns(ns)
        if ns not in self._d:
            self._d[ns] = {}
        return self._d[ns]

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
        return self._d[ns].get(key, default)

    @lock
    def update(self, signature, ns=None):
        """
        Updates the signature with the new signature.
        """
        ns = _get_ns(ns)
        if ns not in self._d:
            self._d[ns] = {}
        self._d[ns][signature.key] = signature

    def save(self, cache):
        """
        Saves this object to ``cache``.
        """
        newd = {}
        for ns, signatures in self._d.items():
            curd = {}
            for key, signature in signatures.items():
                curd[key] = signature
            newd[ns] = curd
        cache.prefix('signaturedb').update(newd)

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
            return  # signature never read thus invalid
        signature.invalidate()

    @lock
    def invalidate_all(self):
        """
        Invalidates all signatures in all namespaces.
        """
        for nsv in self._d.values():
            for sig in nsv.values():
                sig.invalidate()

    @property
    def namespaces(self):
        """
        Returns a list of namespaces.
        """
        return self._d.keys()


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

    def get_signatures(self, ns=None):
        ns = _get_ns(ns)
        if ns not in self._signaturedb:
            self._signaturedb[ns] = {}
        return self._signaturedb[ns]

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

    @property
    def namespaces(self):
        """
        Returns a list of namespaces.
        """
        return self._signaturedb.keys()


class Signature(Serializable):
    """
    A signature is used to compare different versions of nodes.
    For example each time a :class:`wasp.node.FileNode` is changed,
    its signature changes. Thus, by comparing signatures of the same
    nodes, it can be determined if the nodes was changed or not and it
    can be determined if a task has to run again.

    A signature is identified by its ``key`` (for storage), a ``value``
    which is used to compare different versions of nodes and a ``valid``
    flag (e.g. a node is no longer available and thus no value can be assigned
    to its signature).

    :param value: Value of the signature.
    :param valid: Defines whether the signature has a meaningful value.
    :param key: Key to identify the signature. If None, a uuid is assigned.
    """

    def __init__(self, value=None, valid=False, key=None):
        self._value = value
        self._valid = valid
        if key is not None:
            self._key = key
        else:
            self._key = generate_uuid()

    @property
    def key(self):
        """
        Returns the key of the signature for identifying it in storage.
        """
        return self._key

    @property
    def value(self):
        """
        Returns a value corresponding to the content of a node.
        """
        return self._value

    @property
    def valid(self):
        """
        Returns True if the signature is valid and may be compared to
        a previous signature. False otherwise (e.g. if the node is no longer
        availeble).
        """
        return self._valid

    def invalidate(self):
        """
        Sets ``valid`` to False.
        """
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
        """
        Changes the value of the singature.
        """
        raise NotImplementedError

    def clone(self):
        raise NotImplementedError

    def __repr__(self):
        name = self.__class__.__name__
        module = self.__class__.__module__
        return '<' + module + '.' + name + ' = ' + str(self.value) + '>'


class FileSignature(Signature):
    """
    ``FileSignature`` to be used with :class:`wasp.node.FileNode`.

    :param path: Path of the :class:`wasp.node.FileNode`, which is
        set as key.
    """
    def __init__(self, path, value=None, valid=False):
        assert path is not None, 'Path must be given for file signature'
        self.path = path
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
            self._valid = True
            self._value = None
            return None
        if os.path.isdir(self.path):
            # TODO: think about this.... maybe use all the content?!
            # that would be useful for example when packaging a .tgz
            raise RuntimeError('FileSignature cannot be a directory')
        with open(self.path, 'rb') as f:
            data = f.read()
        value = checksum(data)
        self._value = value
        self._valid = True
        return value

    def clone(self):
        return FileSignature(self.path, value=self.value, valid=self.valid)


factory.register(FileSignature)


class CacheSignature(Signature):
    """
    Signature of a part of the ``wasp`` cache. It is used with SymbolicNodes, which
    store their information in the cache.

    :param key: Key for identifying the signature.
    :param prefix: Cache prefix. See :class:`wasp.cache.Cache`.
    """
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
        return cls(d['key'], cache_key=d['key'], prefix=d['prefix']
                   , value=d['value'], valid=d['valid'])

    @lock
    def refresh(self, value=None):
        if value is not None:
            self._value = value
            return value
        if self._cache is None:
            from wasp import ctx
            self._cache = ctx.cache.prefix(self._prefix)
        data = self._cache.get(self._cache_key, None)
        if data is None:
            self._valid = True
            self._value = None
            return None
        jsonarr = factory.to_json(data)
        value = str(json_checksum(jsonarr))
        self._value = value
        self._valid = True
        return value

    def clone(self):
        return CacheSignature(
            self.key, prefix=self._prefix, cache_key=self._cache_key,
            value=self.value, valid=self.valid)


factory.register(CacheSignature)


class UnchangedSignature(Signature):
    """
    A dummy signature which never changes (i.e. comparing it
    to another dummy signature for equality always returns True).
    """

    def to_json(self):
        return None

    @classmethod
    def from_json(cls, d):
        return cls()

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def clone(self):
        return UnchangedSignature()

    def refresh(self, value=None):
        self._valid = True
        self._value = value


factory.register(UnchangedSignature)
