from wasp import ShellTask, find_exe, Task
from wasp import group
from wasp import nodes, FileNode, node
from wasp import file, directory, files
import re


def find_cc(produce=True):
    t = find_exe('gcc', argprefix='cc')
    if produce:
        t.produce(':cpp/cc')
    return t


def find_cxx(produce=True):
    t = find_exe('g++', argprefix='cxx')
    if produce:
        t.produce(':cpp/cxx')
    return t


def find_ld(produce=True):
    t = find_exe('ld', argprefix='ld')
    if produce:
        t.produce(':cpp/ld')
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
        if arg.key in ['cflags', 'include']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        include = self.arguments.get('include', [])
        # relative directories must be mapped relative to self._cwd
        # unless they are given as an absolute path
        include = [directory(x).relative(self._cwd, skip_if_abs=True) for x in include]
        kw['INCLUDE'] = ' -I'.join(include)
        return kw


class CxxCompile(CompileTask):
    cmd = '{CXX} {CFLAGS} {INCLUDE} -c -o {TGT} {SRC}'

    def _init(self):
        super()._init()
        self.require('cxx', spawn=find_cxx)


class CCompile(CompileTask):
    cmd = '{CC} {CFLAGS} {INCLUDE} -c -o {TGT} {SRC}'

    def _init(self):
        super()._init()
        self.require('cc', spawn=find_cc)


class Link(ShellTask):
    cmd = '{LD} {LDFLAGS} {LIBRARIES} -o {TGT} {SRC}'

    def _init(self):
        super()._init()
        self.require('ld', spawn=find_ld)

    def use_arg(self, arg):
        if arg.key in ['ldflags', 'libraries']:
            self.use_catenate(arg)
            return
        super().use_arg(arg)

    def _process_args(self):
        kw = super()._process_args()
        libraries = self.arguments.value('libraries')
        kw['LIBRARIES'] = ' '.join(['-l' + l for l in libraries])
        return kw


def compile(sources, use_default=True):
    ret = []
    for source in nodes(sources):
        assert isinstance(source, FileNode)
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


def link(obj_files, target='main', use_default=True):
    t = Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        t.use(':cpp/ld', libraries=['stdc++'])
    return t
