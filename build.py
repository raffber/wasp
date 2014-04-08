from wasp import ctx
import wasp

@wasp.init
def init():
    ctx.load_tool('d', 'cpp')


@wasp.configure
@wasp.inject_tool('d', 'cpp')
def configure(d, cpp):
    pass

@wasp.build
def build():
    return [
        wasp.ShellTask(sources=ctx.builddir.join('src.txt'),
                     targets=ctx.builddir.join('tgt.txt'),
                     cmd='cp {CPFLAGS} {SRC} {TGT}'),
        d.DProgram(ctx.topdir.join('main.d'), 'mydprog')
    ]