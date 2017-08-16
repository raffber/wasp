from wasp import ctx, shell, Directory, factory, spawn
from wasp import find_exe as find_exe_wasp
from wasp.node import Node
from wasp.signature import Signature
from wasp.util import lock, checksum


# TODO: test with different prefixes
# TODO: test without prefix
# TODO: test with different package versions


def find_npm(produce=True):
    ret = find_exe_wasp('npm', argprefix='npm')
    if produce:
        ret.produce(':nodejs/find-npm')
    return ret


def find_node(produce=True):
    ret = find_exe_wasp('node', argprefix='node')
    if produce:
        ret.produce(':nodejs/find-node')
    return ret


def find_exe(binaryname, prefix=None, argprefix=None, produce=True):
    if isinstance(prefix, str):
        prefix = Directory(prefix)
    if prefix is None:
        prefix = ctx.builddir
    if argprefix is None:
        argprefix = binaryname
    bin_dir = prefix.join('node_modules/.bin')
    ret = find_exe_wasp(binaryname, dirs=bin_dir, argprefix=argprefix)
    if produce:
        ret.produce(':' + argprefix)
    return ret


def _package_key(name, version=None, prefix=None):
    if version is not None:
        key = 'npm://{0}/{1}@{2}'.format(prefix, name, version)
    else:
        key = 'npm://{0}/{1}'.format(prefix, name)
    return key


def package(name, version=None, prefix=None):
    return NpmPackageNode(name, version=version, prefix=prefix)


class NpmPackageNode(Node):
    def __init__(self, name, version=None, prefix=None):
        if isinstance(prefix, str):
            prefix = Directory(prefix)
        if prefix is None:
            prefix = ctx.builddir
        self._prefix = prefix
        self._name = name
        self._version = version
        super().__init__(_package_key(self._name, self._version, self._prefix))

    def _make_signature(self):
        return NpmPackageNodeSignature(self._name, self._version, self._prefix)


class NpmPackageNodeSignature(Signature):
    def __init__(self, name, version, prefix, value=None, valid=True):
        self._name = name
        self._version = version
        self._prefix = prefix
        key = _package_key(name, version, prefix)
        if value is None and valid:
            value = self.refresh()
        super().__init__(value, valid=valid, key=key)

    def to_json(self):
        d = super().to_json()
        d['name'] = self._name
        d['version'] = self._version
        d['prefix'] = str(self._prefix)
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d['name'], d['version'], d['prefix'], value=d['value'], valid=d['valid'])

    @lock
    def refresh(self, value=None):
        if value is not None:
            self._value = value
            self._valid = True
            return value
        f = self._prefix.join('node_modules', self._name, 'package.json')
        if not f.exists:
            self._value = None
            self._valid = False
            return None
        with open(str(f), 'rb') as f:
            data = f.read()
        value = checksum(data)
        self._value = value
        self._valid = True
        return value


factory.register(NpmPackageNodeSignature)


def install(pkg, prefix=None, update=True):
    # TODO: support version
    # TODO: defer update of the package to 'update' task
    # but only if version was not given (otherwise, this does not make much sense)
    if prefix is None:
        prefix = ctx.builddir
    if not isinstance(prefix, str):
        prefix = str(prefix)
    Directory(prefix).mkdir('node_modules')
    cmdline_prefix = _make_prefix(prefix)
    return shell('{npm} --prefix {prefix} install {package}')\
        .use(package=pkg, prefix=cmdline_prefix)\
        .produce(package(pkg, prefix=prefix))\
        .use(spawn(':nodejs/find-npm', find_npm))\
        .require('npm')


def _make_prefix(prefix):
    if str(prefix) == str(ctx.topdir):
        prefix = '.'
    else:
        prefix = prefix
    return prefix
