import wasp
from wasp.fs import defer_install, BINARY_PERMISSIONS, find_exe
from wasp.node import nodes, FileNode
from wasp import ShellTask, osinfo, spawn


class Compile(ShellTask):
    cmd = '{dc} {dflags} -c {src} -of{tgt}'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.require('dc')

    def use_arg(self, arg):
        if arg.name == 'dflags':
            self.use_catenate(arg)
            return
        super().use_arg(arg)


class Link(ShellTask):
    cmd = '{dc} {ldflags} {src} -of{tgt}'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.require('dc')

    def use_arg(self, arg):
        if arg.name == 'ldflags':
            self.use_catenate(arg)
            return
        super().use_arg(arg)


COMPILER_NAMES = ['dmd', 'gdc', 'ldc']
COMPILER_DIRS = []
if osinfo.linux:
    COMPILER_DIRS = ['/usr/bin']


def compile(*sources):
    ret = []
    for source in nodes(sources):
        assert isinstance(source, FileNode)
        target = source.to_file().to_builddir().append_extension('.o')
        task = Compile(sources=source, targets=target)
        ret.append(task)
    return wasp.group(ret).use(spawn(':d/dc', find_dc))


def link(*sources, target='main', install=True):
    f = wasp.File(target)
    if install:
        defer_install(f.to_builddir(), destination='{PREFIX}/bin/', permissions=BINARY_PERMISSIONS)
    return Link(sources=nodes(sources), targets=f.to_builddir()).use(spawn(':d/dc', find_dc))


def find_dc(names=COMPILER_NAMES, dirs=COMPILER_DIRS, produce=True):
    ret = find_exe(*names, dirs=dirs, argprefix='dc').produce(':d/dc')
    if produce:
        ret.produce(':d/dc')
    return ret
