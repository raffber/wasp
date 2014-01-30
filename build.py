from wasp import *

@configure
def configure():
    return ShellTask(sources=ctx.builddir.join('src.txt'),
                     targets=ctx.builddir.join('tgt.txt'),
                     cmd='cp {CPFLAGS} {SRC} {TGT}')
 
