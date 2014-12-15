import wasp
from wasp.fs import defer_install, BINARY_PERMISSIONS
from wasp.node import make_nodes, FileNode


def compile(*sources):
    ret = []
    for source in make_nodes(sources):
        assert isinstance(source, FileNode)
        target = source.to_file().to_builddir().append_extension('.o')
        task = wasp.shell(cmd='{DC} {DFLAGS} -c {SRC} -of{TGT}'
                          , sources=source, targets=target
                          ).require('dc')
        ret.append(task)
    return wasp.group(ret)


def link(*sources, target='main', install=True):
    f = wasp.File(target)
    if install:
        defer_install(f.to_builddir(), destination='{PREFIX}/bin/', permissions=BINARY_PERMISSIONS)
    return wasp.shell(cmd='{DC} {LDFLAGS} {SRC} -of{TGT}'
                      , sources=make_nodes(sources)
                      , targets=f.to_builddir()
                      ).require('dc')
