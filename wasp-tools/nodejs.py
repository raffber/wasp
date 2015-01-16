from wasp import find_exe, ctx, ShellTask, group, quote, shell, Directory


def find_npm():
    return find_exe('npm', argprefix='npm').produce(':node/find-npm')


def find_node():
    return find_exe('node', argprefix='node').produce(':node/find-node')


def find_package_binary(binaryname, prefix=None, argprefix=None):
    if isinstance(prefix, str):
        prefix = Directory(prefix)
    if prefix is None:
        prefix = ctx.builddir
    if argprefix is None:
        argprefix = binaryname
    bin_dir = prefix.join('node_modules/.bin')
    return find_exe(binaryname, dirs=bin_dir, argprefix=argprefix).produce(':' + argprefix)


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
