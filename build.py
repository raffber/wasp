from wasp import ctx
import wasp

d = wasp.tool('d')

@wasp.init
def init():
    ctx.load_tool('d')  # injects the actual tools


@wasp.build
def build():
    pass
    # ret = []
    # cp = wasp.shell('cp {CPFLAGS} {TGT} {SRC}', sources=, targets=)
    # ret += wasp.copy(sources=cp.targets, )
    # ret += d.compile()


