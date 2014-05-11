from wasp import ctx
import wasp

@wasp.init
def init():
    ctx.load_tool('d', 'cpp')


@wasp.build
@wasp.inject_tool('d', 'cpp')
def build(d, cpp):
    ret =  [
        wasp.ShellTask(sources=ctx.builddir.join('src.txt'),
                 targets=ctx.builddir.join('tgt.txt'),
                 cmd='cp {CPFLAGS} {SRC} {TGT}'),
        d.DProgram('main.d', 'mydprog'),
    ]
    return ret
