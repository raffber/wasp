import os
from wasp import ShellTask, find_exe, Task, quote, empty
from wasp import group
from wasp import nodes, FileNode, node, Argument
from wasp import file, directory, osinfo, StringOption
from wasp.shell import run as run_command
from wasp.shell import ShellTaskPrinter

from wasp.util import is_iterable
import wasp
import re


if not osinfo.linux and not osinfo.windows:
    raise ImportError('`cpp` tool does not support your platform')


@wasp.options
def options(opt):
    if osinfo.linux:
        opt.add(StringOption('cc', 'Set the C compiler executable.'))
        opt.add(StringOption('cxx', 'Set the C++ compiler executable.'))
        opt.add(StringOption('ld', 'Set the linker compiler executable.'))
    elif osinfo.windows:
        opt.add(StringOption('msvc-path', 'Set the path to the base folder where MSVC is located.'))
        opt.add(StringOption('msvc-arch', 'Set the architecture to be used for compiling (`x86` or `x64`).'))


class CompilerCli(object):

    def __init__(self, compilername):
        self._name = compilername

    @property
    def position_independent_code(self):
        if self._name in ['gcc', 'clang']:
            return '-fPIC'
        return ''

    def include_dir(self, directory):
        return '-I' + quote(str(directory))

    @property
    def enable_exceptions(self):
        if self._name == 'msvc':
            return '/EHsc'
        return ''

    def defines(self, defines):
        if self._name == 'msvc':
            return ' '.join(['/D"{0}"'.format(d) for d in defines])
        return ' '.join(['-D"{0}"'.format(d) for d in defines])

    def default_flags(self, debug=False, arch=None):
        if self._name == 'msvc':
            if arch == 'x64':
                if debug:
                    return ['/nologo', '/Od', '/MDd', '/W3', '/GS-', '/Z7', '/D_DEBUG']
                return ['/nologo', '/Ox', '/MD', '/W3', '/GS-', '/DNDEBUG']
            else:  # x86 or else
                if debug:
                    return ['/nologo', '/Od', '/MDd', '/W3', '/Z7', '/D_DEBUG']
                return ['/nologo', '/Ox', '/MD', '/W3', '/DNDEBUG']
        return '-std=c++14 ' + ('-O0 -g' if debug else '-O2')


class LinkerCli(object):

    def __init__(self, linkername):
        self._name = linkername

    def link(self, library):
        library = str(library)
        if self._name == 'gcc' or self._name == 'clang':
            if '/' in library or library.startswith('lib'):
                # use the file name directly
                return library
            else:
                # file name is squashed already
                return '-l' + library
        elif self._name == 'msvc':
            return library


if osinfo.windows:
    DEFAULT_COMPILER = 'msvc'
    DEFAULT_LINKER = 'msvc'

    MSVC_VARS = ['VS140COMNTOOLS', 'VS120COMNTOOLS', 'VS100COMNTOOLS', 'VS90COMNTOOLS', 'VS80COMNTOOLS']
    RELEVANT_ENV_VARS = ['lib', 'include', 'path', 'libpath']
    ARCH_VCVARS_ARG = {'x86': 'x86', 'x64': 'amd64'}

    class MsvcError(Exception):
        pass


    class FindMsvc(Task):
        def __init__(self, msvcpath=None, arch=None, debug=False):
            super().__init__()
            self._arch = arch
            if msvcpath is not None:
                self._msvcpath = directory(msvcpath)
            else:
                self._msvcpath = None
            self._env = {}
            self._debug = debug

        def _retrieve_arch(self):
            if osinfo.x64:
                self._arch = 'x64'
            else:
                self._arch = 'x86'

        def _retrieve_msvc(self):
            for varname in MSVC_VARS:
                v = os.environ.get(varname, None)
                if v is not None:
                    if directory(v).exists:
                        self._msvcpath = directory(v).join('../../VC').absolute
                        return

        def _source(self):
            vcvars = self._msvcpath.join('vcvarsall.bat')
            if not vcvars.exists:
                raise MsvcError('`vcvarsall.bat` does not exist in `{0}`. '
                                'Please specify a valid path to MSVC.'.format(self._msvcpath))
            arch = ARCH_VCVARS_ARG.get(self._arch, 'x86')
            exit_code, io = run_command('"{vcvars}" {arch} & set'.format(vcvars=vcvars, arch=arch))
            for line in io.stdout.split('\n'):
                splits = line.strip().split('=')
                if len(splits) != 2:
                    continue
                varname, varvalue = splits[0].lower(), splits[1]
                if varname in RELEVANT_ENV_VARS:
                    subpaths = varvalue.split(os.pathsep)
                    # ignore duplicates
                    self._env[varname] = subpaths
            for var in RELEVANT_ENV_VARS:
                if var not in self._env:
                    raise MsvcError('`vcvarsall.bat` in `{0}` returned '
                                    'an invalid environment.'.format(self._msvcpath))

        def _run(self):
            try:
                if self._arch is None:
                    self._retrieve_arch()
                if self._msvcpath is None:
                    self._retrieve_msvc()
                self._source()
                cl = self._find_exe("cl.exe")
                self._result.update({
                    'cc': cl,
                    'cxx': cl,
                    'ld': self._find_exe("link.exe"),
                    'rc': self._find_exe("rc.exe"),
                    'lib': self._find_exe("lib.exe"),
                    'mc': self._find_exe("mc.exe"),
                    'env': self._env,
                    'arch': self._arch,
                    'debug': self._debug
                })
                self.success = True
            except MsvcError as e:
                self.log.fatal(str(e))
                self.success = False

        def _find_exe(self, name):
            for path in self._env['path']:
                ret = directory(path).join(name)
                if ret.exists:
                    return ret.path
            raise MsvcError('Could not find executable `{0}` '
                            'in environment returned from `vcvarsall.bat`'.format(name))

    def find_cc(use_default=True, debug=False, x64=None):
        if use_default:
            msvcpath = Argument('msvc_path').retrieve_all().value
            if x64 is None:
                arch = Argument('msvc_arch').retrieve_all().value
            else:
                arch = 'x64' if x64 else 'x86'
            t = FindMsvc(msvcpath=msvcpath, arch=arch, debug=debug)
            t.produce(':cpp/cc')
            t.produce(':cpp/cxx')
            t.produce(':cpp/ld')
            return t
        return FindMsvc()

    find_cxx = find_cc
    find_ld = find_cc


    class MsvcCompilerPrinter(ShellTaskPrinter):
        def print(self, success, stdout='', stderr='', exit_code=0, commandstring=''):
            stdout = stdout.split('\n')
            if len(stdout) >= 1:
                stdout = stdout[1:] # discard first line
            stdout = '\n'.join(stdout)
            super().print(success, stdout=stdout, stderr=stderr, exit_code=exit_code, commandstring=commandstring)

    class MsvcLinkerPrinter(ShellTaskPrinter):
        def print(self, success, stdout='', stderr='', exit_code=0, commandstring=''):
            stdout = stdout.split('\n')
            if len(stdout) >= 3:
                stdout = stdout[3:] # discard first three line
            stdout = '\n'.join(stdout)
            super().print(success, stdout=stdout, stderr=stderr, exit_code=exit_code, commandstring=commandstring)


elif osinfo.linux:
    DEFAULT_COMPILER = 'gcc'
    DEFAULT_LINKER = 'gcc'


    def find_cc(debug=False, use_default=True):
        if use_default:
            cc = Argument('cc').retrieve_all().value
            t = find_exe('gcc', argprefix=['cc', 'ld'])
            if cc is None:
                t.use(cc=cc)
            else:
                t = empty().use(cc=cc)
            t.use(debug=debug)
            t.produce(':cpp/cc')
        else:
            t = find_exe('gcc', argprefix=['cc', 'ld'])
        return t


    def find_cxx(debug=False, use_default=True):
        if use_default:
            cxx = Argument('cxx').retrieve_all().value
            t = find_exe('g++', argprefix=['cxx', 'ld'])
            if cxx is None:
                t.use(cxx=cxx)
            else:
                t = empty().use(cxx=cxx)
            t.use(debug=debug)
            t.produce(':cpp/cxx')
        else:
            t = find_exe('g++', argprefix=['cxx', 'ld'])
        return t


class DependencyScan(Task):
    """
    Scans header file dependencies for a *.c or *.cpp file. The paths of the
    headers files are written as a list of strings to the 'headers' field.
    By default, the target node :cpp/headers/<source-path> is used.
    In order to limit the complexity of this task, only one level of header file
    is scanned, i.e. the dependencies are limited to the directly included files
    from the source file.

    :param source: The source file to be scanned.
    :param target: The target node where the result should be written to. If
        None, :cpp/<source-path> is used.
    """

    NUM_LINES = 200
    DEPTH = 10

    def __init__(self, source, target=None):
        f = file(source)
        if target is None:
            target = node(':cpp/{0}'.format(str(f)))
        super().__init__(sources=f, targets=target)
        self._target_node = target
        self._f = f
        self.arguments.add(includes=[])

    def use_arg(self, arg):
        if arg.name == 'includes':
            if is_iterable(arg.value):
                for v in arg.value:
                    self.arguments.value('includes').append(v)
            else:
                v = str(arg.value)
                self.arguments.value('includes').append(v)
            return
        super().use_arg(arg)

    def _run(self):
        headers = set()
        self._scan(headers, self._f, 1)
        headers = set(str(x) for x in headers)
        previous_headers = set(self._target_node.read().value('headers', []))
        new_headers = headers - previous_headers
        self.result['headers'] = list(headers)
        # make sure the new headers are included in the database
        self.targets.extend(nodes(new_headers))
        self.success = True

    def _scan(self, headers, header, current_depth):
        if current_depth > self.DEPTH:
            return set()
        include_re = re.compile('^\s*#include *[<"](?P<include>[0-9a-zA-Z\-_\. /]+)[>"]\s*$')
        num_lines = 0
        if not header.exists:
            return
        with open(str(header), 'r') as f:
            for line in f:
                num_lines += 1
                if num_lines > self.NUM_LINES:
                    break
                m = include_re.match(line)
                if m:
                    include_filepath = m.group('include')
                    self.include_found(header, headers, include_filepath, current_depth)

    def include_found(self, header, headers, include_filepath, current_depth):
        include_paths = list(self.arguments.value('includes', []))
        include_paths.append(directory(header))
        for path in include_paths:
            if directory(path).isabs:
                continue
            f = directory(path).join(include_filepath)
            if f.exists and not f.isdir:
                if f.path in headers:
                    return
                headers.add(f.path)
                self._scan(headers, f, current_depth+1)


class CompileTask(ShellTask):
    extensions = []

    def _init(self):
        self._compilername = DEFAULT_COMPILER
        if self._compilername == 'msvc':
            self._printer = MsvcCompilerPrinter(self)
        csrc = []
        for src in self.sources:
            if not isinstance(src, FileNode):
                continue
            is_csrc = [str(src).endswith(ext) for ext in self.extensions]
            if any(is_csrc):
                csrc.append(str(src))
                headers = node(':cpp/{0}'.format(src)).read().value('headers', [])
                self.sources.extend(nodes(headers))
        self.arguments['csources'] = csrc

    def _prepare(self):
        self._compilername = self.arguments.value('compilername', DEFAULT_COMPILER)
        cli = CompilerCli(self._compilername)
        self.use(cflags=cli.position_independent_code)
        self.use(cflags=cli.enable_exceptions)
        self.use(cflags=cli.default_flags(
            debug=self.arguments.value('debug', False),
            arch=self.arguments.value('arch', None)
        ))

    def use_arg(self, arg):
        if arg.name in ['cflags', 'includes', 'defines']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        include = self.arguments.value('includes', [])
        # relative directories must be mapped relative to self._cwd
        # unless they are given as an absolute path
        cli = CompilerCli(self._compilername)
        include = [cli.include_dir(directory(x).relative(self._cwd, skip_if_abs=True).path) for x in include]
        kw['INCLUDES'] = ' '.join(set(include))
        kw['CFLAGS'] = ' '.join(set(self.arguments.value('cflags', [])))
        kw['CSOURCES'] = ' '.join(set(self.arguments.value('csources', [])))
        defines = self.arguments.value('defines', [])
        kw['DEFINES'] = cli.defines(defines)
        return kw


class CxxCompile(CompileTask):
    extensions = ['cxx', 'cpp', 'c++']

    @property
    def cmd(self):
        if self._compilername == 'msvc':
            return '{CXX} {CFLAGS} {INCLUDES} {DEFINES} /c /Fo{TGT} {CSOURCES}'
        else:
            return '{CXX} {CFLAGS} {INCLUDES} {DEFINES} -c -o {TGT} {CSOURCES}'

    def _init(self):
        super()._init()
        self.require('cxx', spawn=find_cxx)


class CCompile(CompileTask):
    extensions = ['c']

    @property
    def cmd(self):
        if self._compilername == 'msvc':
            return '{CC} {CFLAGS} {INCLUDES} {DEFINES} /c /Fo{TGT} {CSOURCES}'
        else:
            return '{CC} {CFLAGS} {INCLUDES} {DEFINES} -c -o {TGT} {CSOURCES}'

    def _init(self):
        super()._init()
        self.require('cc', spawn=find_cc)


class Link(ShellTask):
    def _init(self):
        super()._init()
        self._linkername = DEFAULT_LINKER
        if self._linkername == 'msvc':
            self._printer = MsvcLinkerPrinter(self)


    def _prepare(self):
        super()._prepare()
        self._linkername = self.arguments.value('linkername', DEFAULT_LINKER)

    @property
    def cmd(self):
        if self._linkername == 'msvc':
            return '{LD} {LDFLAGS} {LIBRARIES} /OUT:{TGT} {SRC}'
        else:
            return '{LD} {LDFLAGS} {LIBRARIES} -o {TGT} {SRC} {STATIC_LIBS}'

    def use_arg(self, arg):
        if arg.name in ['ldflags', 'libraries', 'static_libraries']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        libraries = self.arguments.value('libraries', [])
        cli = LinkerCli(self._linkername)
        libs_cmdline = [cli.link(x) for x in libraries]
        kw['LIBRARIES'] = ' '.join([quote(l) for l in libs_cmdline])
        kw['LDFLAGS'] = ' '.join(set(self.arguments.value('ldflags', [])))
        kw['STATIC_LIBS'] = ' '.join(set(self.arguments.value('static_libraries', [])))
        return kw


def compile(sources, use_default=True):
    ret = []
    for source in nodes(sources):
        if not isinstance(source, FileNode):
            continue
        target = source.to_file().to_builddir().append_extension('.o')
        if source.to_file().extension.lower() == 'c':
            task = CCompile(sources=source, targets=target)
            if use_default:
                task.use(':cpp/cc')
        else:
            # make sure we are a bit failsafe and we just compile unkown
            # file endings with a cxx compiler. There are a lot of
            # esoteric file extensions for cpp out there.
            task = CxxCompile(sources=source, targets=target)
            if use_default:
                task.use(':cpp/cxx')
        ret.append(task)
        dep_scan = DependencyScan(source)
        assert len(dep_scan.targets) >= 1
        header_dep_node = dep_scan.targets[0]
        task.use(header_dep_node)
        for header in header_dep_node.read().value('headers', []):
            task.depends(header)
        ret.append(dep_scan)
    return group(ret)


def link(obj_files, target='main', use_default=True, cpp=True, shared=False):
    t = Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        ldnode = ':cpp/cxx' if cpp else ':cpp/cc'
        spawner = find_cxx if cpp else find_cc
        if osinfo.linux:
            t.use(libraries=['stdc++', 'c', 'pthread'])
        t.use(ldnode).require('ld', spawn=spawner)
    if shared:
        if osinfo.windows:
            t.use(ldflags='/dll')
        else:
            t.use(ldflags='-shared')
    return t
