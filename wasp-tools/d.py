import wasp
from wasp.fs import defer_install, BINARY_PERMISSIONS, Directory, File
from wasp.node import make_nodes, FileNode
from wasp import ShellTask, Task, osinfo


class Compile(ShellTask):
    cmd = '{DC} {DFLAGS} -c {SRC} -of{TGT}'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.require('dc')

    def use_arg(self, arg):
        if arg.key == 'dflags':
            self.use_catenate(arg)
            return
        super().use_arg(arg)


class Link(ShellTask):
    cmd = '{DC} {LDFLAGS} {SRC} -of{TGT}'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.require('dc')

    def use_arg(self, arg):
        if arg.key == 'ldflags':
            self.use_catenate(arg)
            return
        super().use_arg(arg)


COMPILER_NAMES = ['dmd', 'gdc', 'ldc']
COMPILER_DIRS = []
if osinfo.linux:
    COMPILER_DIRS = ['/usr/bin']


class FindCompiler(Task):
    def __init__(self, names=COMPILER_NAMES, dirs=COMPILER_DIRS):
        super().__init__(always=True)
        if isinstance(names, str):
            names = [names]
        if isinstance(dirs, str):
            dirs = [dirs]
        self._names = names
        self._dirs = dirs

    def _run(self):
        for dd in self._dirs:
            d = Directory(dd)
            for name in self._names:
                f = File(d.join(name))
                if f.exists:
                    self.result['dc'] = f.path
                    self.success = True


def compile(*sources):
    ret = []
    for source in make_nodes(sources):
        assert isinstance(source, FileNode)
        target = source.to_file().to_builddir().append_extension('.o')
        task = Compile(sources=source, targets=target)
        ret.append(task)
    return wasp.group(ret)


def link(*sources, target='main', install=True):
    f = wasp.File(target)
    if install:
        defer_install(f.to_builddir(), destination='{PREFIX}/bin/', permissions=BINARY_PERMISSIONS)
    return Link(sources=make_nodes(sources), targets=f.to_builddir())


def find(names=COMPILER_NAMES, dirs=COMPILER_DIRS):
    return FindCompiler(names=names, dirs=dirs)