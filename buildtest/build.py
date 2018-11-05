from wasp import group, shell, tool, configure, chain
from wasp import Directory, nodes
import wasp


latex = tool('latex')
nodejs = tool('nodejs')
cpp = tool('cpp')
qt = tool('qt')


curdir = Directory(__file__)


@configure
def configure():
    c = chain()
    c += nodejs.install('jsmin')
    c += nodejs.find_exe('jsmin').produce(':jsmin')
    yield c


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
    modules = qt.find_modules(keys=[qt.Modules.core, qt.Modules.widgets])
    mocs = qt.moc(headers)
    sources.extend(mocs.targets)
    srcs = nodes(sources)
    objs = qt.compile(srcs).use(modules)
    yield modules
    yield mocs
    yield objs
    yield cpp.link(objs, target=curdir.join('qtmain')).use(modules)
