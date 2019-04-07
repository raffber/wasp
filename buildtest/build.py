import wasp
from wasp import Directory, nodes, shell, chain, Task
from wasp import tool

latex = tool('latex')
cpp = tool('cpp')
qt = tool('qt')


curdir = Directory(__file__)


@wasp.command('cpp')
def _cpp():
    t = cpp.compile('buildtest/main.cpp')
    yield t
    yield cpp.link(t)


@wasp.command('qt', depends='cpp')
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
