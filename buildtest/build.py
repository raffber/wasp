from wasp import group, shell, tool, configure, chain
from wasp import Directory, nodes
import wasp


d = tool('d')
latex = tool('latex')
nodejs = tool('nodejs')
rust = tool('rust')
cpp = tool('cpp')
qt = tool('qt')


curdir = Directory(__file__)


@wasp.build
def main():
    one = d.compile(curdir.join('one.d'))
    two = d.compile(curdir.join('two.d'))
    link = d.link(one, two)
    yield group(one, two, link)


@configure
def configure():
    c = chain()
    c += nodejs.install('jsmin')
    c += nodejs.find_exe('jsmin').produce(':jsmin')
    yield c


@wasp.command('rust')
def _rust():
    return rust.executable('buildtest/main.rs', 'main')


@wasp.command('cpp')
def _cpp():
    t = cpp.compile('buildtest/main.cpp')
    yield t
    yield cpp.link(t)


@wasp.command('nodejs', depends='configure')
def _nodejs():
    for f in curdir.glob('.*?.js$', exclude='build/.*'):
        yield shell('{jsmin} {SRC} > {TGT}', sources=f, targets=f.to_builddir()).use(':jsmin')


@wasp.command('qt')
def _qt():
    headers = [curdir.join('qtmain.h')]
    sources = [curdir.join('qtmain.cpp')]
    modules = qt.find_modules()
    mocs = qt.moc(headers)
    sources.extend(mocs.targets)
    srcs = nodes(sources)
    objs = qt.compile(srcs).use(modules)
    yield modules
    yield mocs
    yield objs
    yield qt.link(objs, target=curdir.join('qtmain')).use(modules)
