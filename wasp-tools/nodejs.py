import json
from wasp import ctx, ShellTask, group, quote, shell, Directory, factory
from wasp.node import Node
from wasp.signature import Signature
from wasp.util import lock
from wasp import find_exe as find_exe_wasp

# TODO: test with different prefixes
# TODO: test without prefix
# TODO: test with different package versions


def find_npm():
    return find_exe_wasp('npm', argprefix='npm').produce(':node/find-npm')


def find_node():
    return find_exe_wasp('node', argprefix='node').produce(':node/find-node')


def find_exe(binaryname, prefix=None, argprefix=None):
    if isinstance(prefix, str):
        prefix = Directory(prefix)
    if prefix is None:
        prefix = ctx.builddir
    if argprefix is None:
        argprefix = binaryname
    bin_dir = prefix.join('node_modules/.bin')
    return find_exe_wasp(binaryname, dirs=bin_dir, argprefix=argprefix).produce(':' + argprefix)


def _package_key(name, version, prefix):
    key = 'npm://{0}/{1}@{2}'.format(prefix, name, version)
    return key


class NpmPackageNode(Node):
    def __init__(self, name, version, prefix=None):
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
        with open(str(f), 'r') as f:
            data = json.load(f)
        # if not os.path.exists(self.path):
        #     self._valid = False
        #     self._value = None
        #     return
        # if os.path.isdir(self.path):
        #     # TODO: think about this.... maybe use all the content?!
        #     # that would be useful for example when packaging a .tgz
        #     self._value = 'directory'
        #     self._valid = True
        #     return self._value
        # with open(self.path, 'rb') as f:
        #     data = f.read()
        # value = checksum(data)
        # self._value = value
        # self._valid = True
        # return value


factory.register(NpmPackageNodeSignature)


class TestInstalled(ShellTask):
    def __init__(self, package, spawn=True):
        super().__init__(always=True)
        self._package = package
        self._installed = None
        self._spawn_install = spawn
        self.arguments['package'] = package
        self.require('npm')

    @property
    def cmd(self):
        return '{npm} {prefix} ls {package}'

    def _finished(self, exit_code, out, err):
        self.success = exit_code == 0 or exit_code == 1
        if not self.success:
            return
        self._installed = exit_code == 0
        self.result['installed'] = self._installed

    def _spawn(self):
        if not self._installed and self._spawn_install:
            return shell('{npm} {prefix} install {package}').use(self.arguments)
        return None


def _make_prefix(prefix):
    if prefix is None:
        prefix = '--prefix ' + quote(ctx.builddir.path)
    elif str(prefix) == str(ctx.topdir):
        prefix = ''
    return prefix


def ensure(*packages, prefix=None):
    ctx.builddir.mkdir('node_modules')
    prefix = _make_prefix(prefix)
    return group([TestInstalled(pkg).use(':node/find-npm', prefix=prefix) for pkg in packages])
