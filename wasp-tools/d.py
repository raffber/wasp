import wasp
from wasp.node import make_node, make_nodes, FileNode


def compile(*sources):
    ret = []
    for source in sources:
        source = make_node(source)
        assert isinstance(source, FileNode)
        target = source.to_file().to_builddir().append_extension('.o')
        task = wasp.shell(cmd='{DC} {DFLAGS} -c {SRC} -of{TGT}'
                          , sources=source, targets=target
                          ).require('dc')
        ret.append(task)
    if len(ret) > 1:
        return wasp.group(ret)
    return ret[0]


def link(*sources, target='main'):
    f = wasp.File(target)
    return wasp.shell(cmd='{DC} {LDFLAGS} {SRC} -of{TGT}'
                      , sources=make_nodes(sources)
                      , targets=f.to_builddir()
                      ).require('dc')
