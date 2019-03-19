import json
import os
from json import JSONDecodeError

from wasp import ShellTask, find_exe, Task, quote, empty, spawn
from wasp import group, TaskFailedError, ctx
from wasp import nodes, FileNode, node, Argument
from wasp import file, directory, osinfo, StringOption, files
from wasp.shell import run as run_command
from wasp.shell import ShellTaskPrinter
from wasp.logging import LogStr

from wasp.util import is_iterable
import wasp
import re


SRC_GLOB = '.*?\.c((pp)|(xx))?$'
HEADER_GLOB = '.*?\.h((pp)|(xx))?$'


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


def glob(*dirs, sources=True, headers=False, exclude=None):
    ret = []
    for d in dirs:
        # ensure that we are dealing with a directory
        # the directory function will raise if there is
        # an issue
        d = directory(d)
        if sources:
            ret.extend(d.glob(SRC_GLOB, exclude=exclude))
        if headers:
            ret.extend(d.glob(HEADER_GLOB, exclude=exclude))
    return ret


def libname(basename):
    basename = str(basename)
    if osinfo.linux:
        if basename.endswith('.so'):
            return basename
        return 'lib' + basename + '.so'
    elif osinfo.windows:
        if basename.endswith('.lib'):
            return basename
        return basename + '.lib'
    raise NotImplementedError


def exename(basename):
    basename = str(basename)
    if osinfo.linux:
        return basename
    elif osinfo.windows:
        if basename.endswith('.exe'):
            return basename
        return basename + '.exe'
    raise NotImplementedError


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

    def default_flags(self, debug=False, arch=None, cxx=False):
        if self._name == 'msvc':
            if arch == 'x64':
                if debug:
                    return ['/nologo', '/Od', '/MDd', '/W3', '/GS-', '/Z7', '/D_DEBUG', '/EHsc']
                return ['/nologo', '/Ox', '/MD', '/W3', '/GS-', '/DNDEBUG', '/EHsc']
            else:  # x86 or else
                if debug:
                    return ['/nologo', '/Od', '/MDd', '/W3', '/Z7', '/D_DEBUG', '/EHsc']
                return ['/nologo', '/Ox', '/MD', '/W3', '/DNDEBUG', '/EHsc']
        return ('-std=c++17 ' if cxx else '') + ('-O0 -g' if debug else '-O3')


class CppPrinter(ShellTaskPrinter):

    def _format_infomsg(self):
        raise NotImplementedError

    def print(self, stdout='', stderr='', exit_code=0):
        t = self._task
        log = t.log
        commandstring = t.commandstring
        if not t.success:
            return_value_format = log.color('  --> ' + str(exit_code), fg='red', style='bright')
            out = stderr.strip()
            if out != '':
                fatal_print = log.format_fail(LogStr(commandstring) + return_value_format, out)
            else:
                fatal_print = log.format_fail(LogStr(commandstring) + return_value_format)
            log.fatal(fatal_print)
        elif stderr != '':
            warn_print = log.format_warn(LogStr(commandstring), stderr.strip())
            log.warn(warn_print)
        if t.success:
            t.log.info(self._format_infomsg())
            t.log.debug(t.log.format_success() + commandstring)
        if stdout != '':
            out = log.format_info(stdout.strip())
            log.info(out)


class CompilePrinter(CppPrinter):
    def _format_infomsg(self):
        prepend = self._task.log.format_success()
        return prepend + 'Compiled: ' + self._task.arguments.value('csource', '')


class LinkPrinter(CppPrinter):
    def _format_infomsg(self):
        prepend = self._task.log.format_success()
        tgt_path = None
        for t in self._task.targets:
            if isinstance(t, FileNode):
                tgt_path = t.to_file().relative(ctx.topdir, skip_if_abs=True).path
                break
        return prepend + 'Linked: ' + tgt_path


if osinfo.windows:
    DEFAULT_COMPILER = 'msvc'
    DEFAULT_LINKER = 'msvc'

    MSVC_VARS = ['VS140COMNTOOLS', 'VS120COMNTOOLS', 'VS100COMNTOOLS', 'VS90COMNTOOLS', 'VS80COMNTOOLS']
    RELEVANT_ENV_VARS = ['lib', 'include', 'path', 'libpath']
    ARCH_VCVARS_ARG = {'x86': 'x86', 'x64': 'amd64'}
    VSWHERE_PATH = 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\vswhere.exe'

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
            # detect up to MSVC 2017
            for varname in MSVC_VARS:
                v = os.environ.get(varname, None)
                if v is not None:
                    if directory(v).exists:
                        self._msvcpath = directory(v).join('../../VC').absolute
                        return
            # MVSC 2017
            if not file(VSWHERE_PATH).exists:
                return
            exit_code, out = run_command(quote(VSWHERE_PATH) + ' -latest -format json')
            data = json.loads(out.stdout)
            install_path = data[0]['installationPath']
            # ponit to where vcvarsall.bat is located
            self._msvcpath = directory(install_path).join('VC/Auxiliary/Build')


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
                # else:
                #     self._env[varname] = varvalue
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


    class MsvcCompilerPrinter(CompilePrinter):
        def print(self, stdout='', stderr='', exit_code=0):
            stdout = stdout.split('\n')
            if len(stdout) >= 1:
                stdout = stdout[1:]  # discard first line
            stdout = '\n'.join(stdout)
            super().print(stdout=stdout, stderr=stderr, exit_code=exit_code)

    class MsvcLinkerPrinter(LinkPrinter):
        def print(self, stdout='', stderr='', exit_code=0):
            stdout = stdout.split('\n')
            if len(stdout) >= 3:
                stdout = stdout[3:]  # discard first three line
            stdout = '\n'.join(stdout)
            super().print(stdout=stdout, stderr=stderr, exit_code=exit_code)


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


class CompileTask(ShellTask):
    extensions = []
    require_keys = []

    def __init__(self, source=None, target=None, scan_ignore=None, use_default=True, scan=True):
        super().__init__(sources=source, targets=target)
        self._use_default = use_default
        self._depfile = None
        self._new_headers = set()
        self._old_headers = set()
        if scan_ignore is not None:
            if not is_iterable(scan_ignore):
                scan_ignore = [scan_ignore]
            scan_ignore = [re.compile(x) for x in scan_ignore]
        else:
            scan_ignore = [re.compile('/usr/include.*?')]
        self._scan_ignore = scan_ignore
        self._scan = scan
        tgt_files = files(self._targets)
        if len(tgt_files) == 0:
            raise ValueError('CompileTask: Must be given an object file as compile target')
        self._obj = tgt_files[0]
        for req in self.require_keys:
            self.require(req)
        self._compilername = DEFAULT_COMPILER
        if self._compilername == 'msvc':
            self._printer = MsvcCompilerPrinter(self)
        else:
            self._printer = CompilePrinter(self)
        for src in self.sources:
            if not isinstance(src, FileNode):
                continue
            src = file(src)
            is_csrc = [str(src).endswith(ext) for ext in self.extensions]
            if any(is_csrc):
                self.arguments['csource'] = str(src)
                self._depfile = file(self._obj.directory().join(src.basename + '.d'))
                header_node = node(':cpp/{0}'.format(src.path))
                self._headers = header_node.read().value('headers', [])
                self._old_headers = set(str(x) for x in self._headers)
                self.sources.extend(nodes(self._headers))
                if self._scan:
                    self.targets.append(header_node)
                break

    def _prepare(self):
        self._compilername = self.arguments.value('compilername', DEFAULT_COMPILER)
        if self._use_default:
            cli = CompilerCli(self._compilername)
            self.use(cflags=cli.position_independent_code)
            self.use(cflags=cli.enable_exceptions)

    def use_arg(self, arg):
        if arg.key in ['cflags', 'includes', 'defines']:
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
        kw['includes'] = ' '.join(set(include))
        kw['cflags'] = ' '.join(set(self.arguments.value('cflags', [])))
        csource = self.arguments.value('csource', None)
        if csource is None:
            raise TaskFailedError('No sources recognized. Are your source files '
                                  'using the right extensions? Expected one of [{}]'
                                  .format(', '.join(self.extensions)))
        kw['csource'] = quote(csource)
        defines = self.arguments.value('defines', [])
        kw['defines'] = cli.defines(set(defines))
        kw['obj'] = quote(self._obj.path)
        return kw

    def _read_depfile(self):
        with open(self._depfile.path) as f:
            deps = f.read()
        deps = deps.replace('\\\n', ' ')
        splits = re.split(r'(?<!\\)\s+', deps)
        splits = splits[1:]  # ignore make rule
        headers = set()
        for hdr in splits:
            if hdr == '':
                continue
            ignore = False
            for ignore_re in self._scan_ignore:
                m = ignore_re.match(hdr)
                if m:
                    ignore = True
                    break
            if ignore:
                continue
            headers.add(hdr)
        self._new_headers = headers - self._old_headers
        self.result['headers'] = list(sorted(headers))

    def _on_success(self):
        if self._scan:
            self._read_depfile()
        super()._on_success()

    @property
    def new_nodes(self):
        return self._new_headers


class CxxCompile(CompileTask):
    extensions = ['cxx', 'cpp', 'c++', 'cc']
    require_keys = ['cxx']

    def _prepare(self):
        super()._prepare()
        if self._use_default:
            cli = CompilerCli(self._compilername)
            self.use(cflags=cli.default_flags(
                debug=self.arguments.value('debug', False),
                arch=self.arguments.value('arch', None),
                cxx=True
            ))

    @property
    def cmd(self):
        if self._compilername == 'msvc':
            return '{cxx} {cflags} {cxxflags} {includes} {defines} /c /Fo{obj} /Tp{csource}'
        else:
            return '{cxx} {cflags} {cxxflags} {includes} {defines} -MMD -c -o {obj} {csource}'


class CCompile(CompileTask):
    extensions = ['c']
    require_keys = ['cc']

    def _prepare(self):
        super()._prepare()
        if self._use_default:
            cli = CompilerCli(self._compilername)
            self.use(cflags=cli.default_flags(
                debug=self.arguments.value('debug', False),
                arch=self.arguments.value('arch', None),
                cxx=False
            ))

    @property
    def cmd(self):
        if self._compilername == 'msvc':
            return '{cc} {cflags} {includes} {defines} /c /Fo{tgt} /Tc{csource}'
        else:
            return '{cc} {cflags} {includes} {defines} -MMD -c -o {tgt} {csource}'

    def postprocess(self):
        pass


class Link(ShellTask):

    def __init__(self, sources=None, target=None):
        super().__init__(sources=sources, targets=target)
        self._linkername = DEFAULT_LINKER
        if self._linkername == 'msvc':
            self._printer = MsvcLinkerPrinter(self)
        else:
            self._printer = LinkPrinter(self)
        self.require('ld')

    def _prepare(self):
        super()._prepare()
        self._linkername = self.arguments.value('linkername', DEFAULT_LINKER)
        libraries = []
        for t in self.targets:
            if isinstance(t, FileNode):
                libraries.append(t.to_file().path)
        self.result['libraries'] = libraries

    @property
    def cmd(self):
        if self._linkername == 'msvc':
            return '{ld} {ldflags} {libraries} {src} {static_libs} /OUT:{lnk_tgt}'
        else:
            return '{ld} {ldflags} {lib_includes} -o {tgt} {src} {static_libs} {libraries}'

    def use_arg(self, arg):
        if arg.key in ['ldflags', 'libraries', 'static_libraries']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        lib_includes = set()
        libraries = []
        for lib in self.arguments.value('libraries', []):
            lib = str(lib)
            if '/' in lib:
                libfile = file(lib)
                libdir = file(libfile.absolute).directory()
                lib_includes.add(libdir.path)
                lib = libfile.basename
            if lib.startswith('lib') and '.so.' not in lib:
                # if .so.x.y.z then link absolute
                # else link directly with -l
                if lib.endswith('.so'):
                    lib = lib[:-3]
                libraries.append('-l' + lib[3:])
            else:
                libraries.append('-l:' + lib)
        static_libs = self.arguments.value('static_libraries', [])
        kw['lib_includes'] = ' '.join('-L' + quote(include) for include in lib_includes)
        kw['libraries'] = ' '.join(quote(l) for l in libraries)
        kw['ldflags'] = ' '.join(set(self.arguments.value('ldflags', [])))
        kw['static_libs'] = ' '.join(str(x) for x in static_libs)
        kw['lnk_tgt'] = kw['tgt'].replace('.lib', '.dll')  # TODO: not nice...
        return kw


def compile(sources, bd_path=None, use_default=True, scan_ignore=None, scan=True):
    ret = []
    for source in nodes(sources):
        if not isinstance(source, FileNode):
            continue
        if bd_path is None:
            target = source.to_file().to_builddir().append_extension('.o')
        else:
            target = file(bd_path.join(source)).append_extension('.o')
        if source.to_file().extension.lower() == 'c':
            task = CCompile(source=source, target=target, use_default=use_default, scan_ignore=scan_ignore, scan=scan)
            if use_default:
                task.use(spawn(':cpp/cc', find_cc))
        else:
            # make sure we are a bit failsafe and we just compile unkown
            # file endings with a cxx compiler. There are a lot of
            # esoteric file extensions for cpp out there.
            task = CxxCompile(source=source, target=target, use_default=use_default, scan_ignore=scan_ignore, scan=scan)
            if use_default:
                task.use(spawn(':cpp/cxx', find_cxx))
        ret.append(task)
    return group(ret)


def link(obj_files, target=None, use_default=True, cpp=True, shared=False):
    if target is None:
        target = 'main'
    if use_default:
        if shared:
            target = libname(target)
        else:
            target = exename(target)
    sources = []
    for src in nodes(obj_files):
        if isinstance(src, FileNode) and file(src).extension == 'o':
            sources.append(src)
    t = Link(sources=sources, target=file(target).to_builddir())
    if use_default:
        spawner = find_cxx if cpp else find_cc
        if osinfo.linux:
            t.use(libraries=['libstdc++', 'libc', 'libpthread'])
        ldnode = spawn(':cpp/cxx' if cpp else ':cpp/cc', spawner)
        t.use(ldnode)
    if shared:
        if osinfo.windows:
            t.use(ldflags='/dll')
        else:
            t.use(ldflags='-shared')
    return t


class CompileInfoTask(Task):
    CATENATE_KEYS = ['cflags', 'includes', 'defines', 'ldflags', 'libraries', 'static_libraries']

    def __init__(self, fname, excludes):
        super().__init__()
        self._fname = str(fname)
        self._excludes = excludes

    def use_arg(self, arg):
        if arg.key in self.CATENATE_KEYS:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def run(self):
        args = []
        for k, v in self.arguments.items():
            if k in self._excludes:
                continue
            if k == 'includes':
                absolutified = [directory(x).absolute.path for x in v.value]
                v = Argument(k)
                v.value = absolutified
            if k in ['libraries', 'static_libraries']:
                libs = []
                for x in v.value:
                    strx = str(x)
                    # detect whether we are dealing with a file path
                    # or with a global library reference
                    # a bit of heuristic ;(
                    if os.path.sep in strx:
                        libs.append(file(x).absolute.path)
                        continue
                    libs.append(strx)
                v = Argument(k)
                v.value = libs
            args.append(v.to_json())
        with open(self._fname, 'w') as f:
            json.dump(args, f)
        self.success = True


def write_compile_info(fname=None, excludes=None):
    if fname is None:
        fname = file('compile_info.json').to_builddir()
    if excludes is None:
        excludes = []
    return CompileInfoTask(fname, excludes)


def read_compile_info(fname=None):
    if fname is None:
        fname = file('compile_info.json').to_builddir()

    def task_fun(t):
        with open(str(fname)) as f:
            try:
                lst = json.load(f)
            except JSONDecodeError:
                t.log.log_fail('Invalid compile info. File should be a valid json file.')
                return
            if not isinstance(lst, list):
                t.log.log_fail('Invalid compile info. Expected a list in json file.')
                return
            for item in lst:
                t.result.add(Argument.from_json(item))
        t.success = True
    return Task(fun=task_fun, sources=fname)
