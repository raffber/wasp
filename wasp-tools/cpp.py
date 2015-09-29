from wasp import ShellTask, find_exe, Task, quote
from wasp import group
from wasp import nodes, FileNode, node
from wasp import file, directory, osinfo
from wasp.util import is_iterable
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
        None, :cpp/<source-path> is used.
    """

    NUM_LINES = 200
    DEPTH = 10

    def __init__(self, source, target=None):
        f = file(source)
        if target is None:
            target = node(':cpp/{0}'.format(str(f)))
        super().__init__(sources=f, targets=target)
        self._f = f
        self.arguments.add(includes=[])

    def use_arg(self, arg):
        if arg.key == 'includes':
            if is_iterable(arg.value):
                for v in arg.value:
                    self.arguments.value('includes').append(v)
            else:
                assert isinstance(arg.value, str)
                self.arguments.value('includes').append(arg.value)
            return
        super().use_arg(arg)

    def _run(self):
        headers = set()
        self._scan(headers, self._f, 1)
        self.result['headers'] = list(str(x) for x in headers)
        self.success = True

    def _scan(self, headers, header, current_depth):
        if current_depth > self.DEPTH:
            return set()
        include_re = re.compile('^\s*#include *[<"](?P<include>[0-9a-zA-Z\-_\. /]+)[>"]\s*$')
        num_lines = 0
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

    def _init(self):
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
        kw['CFLAGS'] = ' '.join(set(self.arguments.value('cflags', [])))
        kw['CSOURCES'] = ' '.join(set(self.arguments.value('csources')))
        return kw


class CxxCompile(CompileTask):
    extensions = ['cxx', 'cpp', 'c++']
    cmd = '{CXX} {CFLAGS} {INCLUDES} -c -o {TGT} {CSOURCES}'

    def _init(self):
        super()._init()
        self.require('cxx', spawn=find_cxx)


class CCompile(CompileTask):
    extensions = ['c']
    cmd = '{CC} {CFLAGS} {INCLUDES} -c -o {TGT} {CSOURCES}'

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
        kw['LDFLAGS'] = ' '.join(set(self.arguments.value('ldflags', [])))
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


def link(obj_files, target='main', use_default=True, cpp=True):
    t = Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        ldnode = ':cpp/cxx' if cpp else ':cpp/cc'
        spawner = find_cxx if cpp else find_cc
        t.use(ldnode, libraries=['stdc++', 'c']).require('ld', spawn=spawner)
    return t
