import re
from wasp import nodes, shell, group, file, tool, Task, Argument, osinfo, directory, options, spawn
from wasp import StringOption
from wasp.fs import FindTask

_cpp = tool('cpp')


@options
def inject_options(opt):
    opt.add(StringOption('qt-lib-dir', description='Directory containing Qt libraries.'))
    opt.add(StringOption('qt-include-dir', description='Directory containing Qt include files.'))
    opt.add(StringOption('qt-bin-dir', description='Directory containing Qt binaries such as the MOC.'))
    opt.add(StringOption('qt-base-dir', description='Base directory for Qt (installation directory on Windows)'))


class FindMoc(FindTask):

    def __init__(self, mocpath=None, dirs=None):
        if mocpath is None:
            self._mocpath = None
            if osinfo.linux:
                name = 'moc-qt5'
            else:
                name = 'moc.exe'
            super().__init__(name, argprefix='moc', dirs=dirs)
        else:
            assert isinstance(mocpath, str)
            self._mocpath = mocpath
            super().__init__(argprefix='moc')

    def _prepare(self):
        super()._prepare()
        bin_dir = self.arguments.value('bin_dir')
        if bin_dir is not None:
            self._dirs = [directory(bin_dir)]

    def _run(self):
        if self._mocpath is None:
            super()._run()
            return
        if not file(self._mocpath).exists:
            self.log.fatal('qt.FindMoc: {0} does not exist'.format(self._mocpath))
            self.success = False
            return
        self.result.update(**{self._argprefix: self._mocpath})
        self.success = True


def find_moc(bin_dir=None, use_default=True):
    dirs = None
    if bin_dir is None and use_default:
        bin_dir = bin_dir or Argument('qt_bin_dir').retrieve_all().value
        if bin_dir is not None:
            dirs = [bin_dir]
    moc = Argument('qt_moc').retrieve_all().value
    t = FindMoc(mocpath=moc, dirs=dirs)
    if use_default:
        t.produce(':qt/moc')
        t.use(':qt/config')
    return t


def windows_find_basedir():
    qtdir_re = re.compile('qt(?P<version>5\.([0-9\.])+)')
    installdir = None
    version = None
    for p in directory('C:/Qt/').list():
        m = qtdir_re.match(p.basename.lower())
        if p.isdir and m is not None:
            installdir = p
            version = m.group('version')
            break
    if installdir is None:
        return None
    version_dir = installdir.join(version)
    if not version_dir.exists:
        return
    for p in version_dir.list():
        if 'msvc' in p.basename.lower():
            return str(p)
    return None


class FindQt(Task):

    def __init__(self, include_dir=None, lib_dir=None, bin_dir=None, base_dir=None):
        super().__init__()
        self._include_dir = include_dir
        self._lib_dir = lib_dir
        self._bin_dir = bin_dir
        self._base_dir = base_dir

    def _run(self):
        include_dir = self._include_dir
        lib_dir = self._lib_dir
        bin_dir = self._bin_dir
        base_dir = self._base_dir
        if osinfo.linux:
            data = {
                'include_dir': include_dir or '/usr/include/qt',
                'lib_dir': lib_dir or '/usr/lib',
                'bin_dir': bin_dir or '/usr/bin',
                'base_dir': base_dir or '/usr/share/qt'
            }
        elif osinfo.windows:
            if include_dir is not None:
                self.log.log_warn('qt.FindQt: setting include_dir with find_qt() is ignored. Use base_dir=... instead.')
            if base_dir is None:
                base_dir = windows_find_basedir()
                if base_dir is not None:
                    self.log.log_info('qt.FindQt: Automatically found qt in `{}`'.format(base_dir))
                else:
                    self.log.log_fatal('qt.FindQt: Could not find Qt base dir. Either specify or copy qt to C:\\Qt\\<version>\\<compiler>')
                    self.success = False
                    return
            data = {
                'include_dir': include_dir or directory(base_dir).join('include').path,
                'lib_dir': lib_dir or directory(base_dir).join('lib').path,
                'bin_dir': bin_dir or directory(base_dir).join('bin').path,
                'base_dir': base_dir
            }
        else:
            self.log.fatal('qt.FindQt: Your platform is not supported!')
            self.success = False
            data = {}
        self.success = True
        self.result.update(data)


def find_qt(use_default=True, include_dir=None, lib_dir=None, bin_dir=None, base_dir=None):
    if use_default:
        include_dir = include_dir or Argument('qt_include_dir').retrieve_all().value
        lib_dir = lib_dir or Argument('qt_lib_dir').retrieve_all().value
        bin_dir = bin_dir or Argument('qt_bin_dir').retrieve_all().value
        base_dir = base_dir or Argument('qt_base_dir').retrieve_all().value
    else:
        include_dir = None
        lib_dir = None
        bin_dir = None
        base_dir = None
    t = FindQt(include_dir=include_dir, lib_dir=lib_dir, bin_dir=bin_dir, base_dir=base_dir)
    if use_default:
        t.produce(':qt/config')
    return t


class Modules(object):
    core = 'Core'
    gui = 'Gui'
    widgets = 'Widgets'
    qml = 'Qml'
    quick = 'Quick'
    quick_widgets = 'QuickWidgets'

    @classmethod
    def filename(cls, lib_dir, key):
        if osinfo.windows:
            return directory(lib_dir).join('Qt5' + key + '.lib').path
        elif osinfo.linux:
            return directory(lib_dir).join('libQt5' + key + '.so').path

    @classmethod
    def includedir(cls, include_dir, key):
        include_dir = directory(include_dir)
        return [include_dir.join('Qt' + key), include_dir]


class FindModules(Task):

    def __init__(self, keys, base_dir=None, include_dir=None, lib_dir=None):
        super().__init__()
        self.use(base_dir=base_dir, include_dir=include_dir, lib_dir=lib_dir)
        self.require('base_dir', 'include_dir', 'lib_dir')
        self._keys = keys

    def _run(self):
        include_dir = self.arguments.value('include_dir')
        lib_dir = self.arguments.value('lib_dir')
        assert include_dir is not None and lib_dir is not None
        includes = []
        libraries = []
        lib_dir = directory(lib_dir)
        for key in self._keys:
            fname = Modules.filename(lib_dir, key)
            if not lib_dir.join(fname).exists:
                self.log.fatal('qt.FindModules: Could not find shared object at `{0}`'
                               .format(lib_dir.join(fname)))
                self.success = False
                return
            libraries.append(fname)
            include_paths = Modules.includedir(include_dir, key)
            for path in include_paths:
                if not file(path).exists:
                    self.log.fatal('qt.FindModules: Could not find include directories at `{0}`'
                                   .format(', '.join(x.path for x in include_paths)))
                    self.success = False
                    return
            includes.extend(include_paths)
        self.result['includes'] = includes
        self.result['libraries'] = libraries
        self.success = True


def find_modules(use_default=True, include_dir=None, lib_dir=None, base_dir=None, keys=None):
    if keys is None:
        keys = [Modules.core]
    if use_default:
        include_dir = include_dir or Argument('qt_include_dir').retrieve_all().value
        lib_dir = lib_dir or Argument('qt_lib_dir').retrieve_all().value
        base_dir = lib_dir or Argument('qt_base_dir').retrieve_all().value
    t = FindModules(keys, include_dir=include_dir, lib_dir=lib_dir, base_dir=base_dir)
    if use_default:
        t.produce(':qt/modules')
        t.use(spawn(':qt/config', find_qt))
    return t


def moc(fs, use_default=True):
    fs = nodes(fs)
    ret = []
    for f in fs:
        tgt = file(f).to_builddir().append_extension('moc.cpp')
        t = shell(cmd='{moc} -o {tgt} {src}', sources=f.to_file(), targets=tgt)
        t.require('moc')
        if use_default:
            t.use(spawn(':qt/moc', find_moc))
        ret.append(t)
    return group(ret)


def compile(sources, use_default=True):
    ret = _cpp.compile(sources, use_default=use_default)
    return ret


def program(fs):
    ret = []
    fs = nodes(fs)
    mocs = moc(fs)
    ret.append(mocs)
    fs.extend(mocs.targets)
    ret.append(compile(fs))
