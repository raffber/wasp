from wasp import *

dtool = None

@init
def init():
    dtool = ctx.tool('d')

@configure
def configure():
    return ShellTask(sources=ctx.builddir.join('src.txt'),
                     targets=ctx.builddir.join('tgt.txt'),
                     cmd='cp {CPFLAGS} {SRC} {TGT}')
 
