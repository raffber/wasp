from wasp import ctx, File, group, shell
import wasp


@wasp.init
def init():
    ctx.load_tool('d')

@wasp.build
def build():
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
                    sources=f, targets=f.to_builddir()
                    ).use(cpflags='-r')
    d = ctx.tool('d')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    return cp, group(one, two, link).use(dc='/usr/lib/dmd')

