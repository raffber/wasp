from wasp import find_exe, ctx, ShellTask, group, quote, shell

import json


def find_npm():
    return find_exe('npm', argprefix='npm').produce(':node/find-npm')


def find_node():
    return find_exe('node', argprefix='node').produce(':node/find-node')


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
        return 'npm_config_json=true {npm} {prefix} ls {package}'

    def _finished(self, exit_code, out, err):
        self.success = exit_code == 0
        if not self.success:
            return
        try:
            data = json.loads(out)
        except ValueError:
            self.success = False
            self.log.fatal(self.log.format_fail(
                'Expected JSON result while executing:',
                self._format_cmd(),
                'Result was',
                out))
            return
        self._installed = len(data) != 0
        self.result['installed'] = self._installed

    def _spawn(self):
        if not self._installed and self._spawn_install:
            return shell('npm_config_json=true {npm} {prefix} install {package}').use(self.arguments)
        return None


def ensure(*packages, prefix=None):
    ctx.builddir.mkdir('node_modules')
    if prefix is None:
        prefix = '--prefix ' + quote(ctx.builddir.path)
    elif str(prefix) == str(ctx.topdir):
        prefix = ''
    return group([TestInstalled(pkg).use(prefix=prefix) for pkg in packages])
