from wasp import ShellTask, find_exe, Task, quote
from wasp import group
from wasp import nodes, FileNode, node
from wasp import file, directory, osinfo
import re


def find_cc(produce=True):
    t = find_exe('gcc', argprefix=['cc', 'ld'])
    if produce:
        t.produce(':cpp/cc')
    return t


def find_cxx(produce=True):
    t = find_exe('g++', argprefix=['cxx', 'ld'])
    if produce:
        t.produce(':cpp/cxx')
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
        None, :cpp/headers/<source-path> is used.
    """

    def __init__(self, source, target=None):
        f = file(source)
        if target is None:
            target = node(':cpp/headers/{0}'.format(str(f)))
        super().__init__(sources=f, targets=target)
        self._f = f

    def _run(self):
        include_re = re.compile('^\s*#include *[<"](?P<include>[0-9a-zA-Z\-_\. /]+)[>"]\s*$')
        num_lines = 0
        headers = []
        dir = self._f.directory()
        with open(str(self._f), 'r') as f:
            for line in f:
                num_lines += 1
                if num_lines > 200:
                    break
                m = include_re.match(line)
                if m:
                    include_filepath = m.group('include')
                    f = dir.join(include_filepath)
                    # TODO: scan over include path here
                    if not f.exists:
                        continue
                    headers.append(str(f))
        self.result['headers'] = headers
        self.success = True


class CompileTask(ShellTask):
    def use_arg(self, arg):
        if arg.key in ['cflags', 'includes']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        include = self.arguments.value('includes', [])
        # relative directories must be mapped relative to self._cwd
        # unless they are given as an absolute path
        include = ['-I' + directory(x).relative(self._cwd, skip_if_abs=True).path for x in include]
        kw['INCLUDES'] = ' '.join(set(include))
        kw['CFLAGS'] = ''.join(set(self.arguments.value('cflags', [])))
        return kw


class CxxCompile(CompileTask):
    cmd = '{CXX} {CFLAGS} {INCLUDES} -c -o {TGT} {SRC}'

    def _init(self):
        super()._init()
        self.require('cxx', spawn=find_cxx)


class CCompile(CompileTask):
    cmd = '{CC} {CFLAGS} {INCLUDES} -c -o {TGT} {SRC}'

    def _init(self):
        super()._init()
        self.require('cc', spawn=find_cc)


class Link(ShellTask):
    cmd = '{LD} {LDFLAGS} {LIBRARIES} -o {TGT} {SRC}'

    def use_arg(self, arg):
        if arg.key in ['ldflags', 'libraries']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        libraries = self.arguments.value('libraries')
        # libraries = [l[3:] if l.startswith('lib') else l for l in libraries]
        libs_cmdline = []
        if osinfo.linux:
            for l in libraries:
                if '/' in l or l.startswith('lib'):
                    # use the file name directly
                    libs_cmdline.append(l)
                else:
                    # file name is squashed already
                    libs_cmdline.append('-l' + l)
        else:
            raise NotImplementedError  # TODO ...
        kw['LIBRARIES'] = ' '.join([quote(l) for l in libs_cmdline])
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
    return group(ret)


def link(obj_files, target='main', use_default=True, cpp=True):
    t = Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        ldnode = ':cpp/cxx' if cpp else ':cpp/cc'
        spawner = find_cxx if cpp else find_cc
        t.use(ldnode, libraries=['stdc++', 'c']).require('ld', spawn=spawner)
    return t
