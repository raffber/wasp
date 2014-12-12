from wasp import ctx, File, group, shell, tool
import wasp


d = tool('d')


@wasp.init
def init():
    ctx.load_tool('d', path='wasp-tools')


@wasp.build
def build():
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
               sources=f, targets=f.to_builddir()
               ).use(cpflags='-r')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    return cp, group(one, two, link).use(dc='/usr/bin/dmd')

