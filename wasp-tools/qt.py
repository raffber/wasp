from wasp import nodes, shell, group, find_exe, file, tool, Directory, Task, find
from wasp.task import empty

_cpp = tool('cpp')

INCLUDE_DIR = '/usr/include/qt/'
LIB_DIR = '/usr/lib'


def find_moc(produce=True):
    t = find_exe('moc-qt5', argprefix='moc')
    if produce:
        t.produce(':qt/moc')
    return t


class Modules(object):
    core = 'Core'
    gui = 'Gui'
    widgets = 'Widgets'
    qml = 'Qml'
    quick = 'Quick'
    quick_widgets = 'QuickWidgets'


class CollectorTask(Task):

    def _run(self):
        self.result = self.arguments
        self.success = True

    @property
    def always(self):
        return True

    def use_arg(self, arg):
        if arg.key in ['includes', 'libraries']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)


def find_modules(includedir=INCLUDE_DIR, libdir=LIB_DIR, keys=[Modules.core]):
    ret = []
    collector = CollectorTask()
    for key in keys:
        lowerkey = key.lower()
        lib = find('libQt5'+key + '.so', dirs=libdir, argprefix='libraries')
        include_path = Directory(includedir).join('Qt' + key)
        lib.produce(':qt/lib/' + lowerkey)
        ret.append(lib)
        collector.use(lib).use(includes=include_path)
    collector.use(includes=includedir)
    ret.append(collector)
    return group(ret, target_task=collector)


def moc(fs):
    fs = nodes(fs)
    ret = []
    for f in fs:
        tgt = file(f).to_builddir().append_extension('moc.cpp')
        t = shell(cmd='{MOC} -o {TGT} {SRC}', sources=f.to_file(), targets=tgt)
        t.require('moc', spawn=find_moc)
        ret.append(t)
    return group(ret)


def compile(sources, use_default=True):
    ret = _cpp.compile(sources, use_default=use_default)
    ret.use(cflags='-fPIC')
    return ret


def program(fs):
    ret = []
    fs = nodes(fs)
    mocs = moc(fs)
    ret.append(mocs)
    fs.extend(mocs.targets)
    ret.append(compile(fs))


def link(obj_files, target='main', use_default=True):
    t = _cpp.Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        ldnode = ':cpp/cxx'
        spawner = _cpp .find_cxx
        t.use(ldnode, libraries=['stdc++', 'c']).require('ld', spawn=spawner)
    return t
