from .task import Task
from .node import FileNode
from .argument import Argument
from .util import UnusedArgFormatter, is_iterable
from .logging import LogStr
from .fs import Directory

from io import StringIO
from subprocess import Popen, PIPE


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd='', always=False, cwd=None):
        super().__init__(sources=sources, targets=targets, children=children, always=always)
        self._cmd = cmd
        if cwd is None:
            self._cwd = None
        else:
            self._cwd = Directory(cwd, make_absolute=True).path

    @property
    def cwd(self):
        return self._cwd

    @property
    def cmd(self):
        return self._cmd

    def _finished(self, exit_code, out, err):
        self.success = exit_code == 0

    def _process_args(self):
        src_list = []
        for s in self.sources:
            if isinstance(s, FileNode):
                src_list.append(s.path)
        tgt_list = []
        for t in self.targets:
            if isinstance(t, FileNode):
                tgt_list.append(t.path)
        src_str = ' '.join(src_list)
        tgt_str = ' '.join(tgt_list)
        kw = {'SRC': src_str,
              'TGT': tgt_str}
        for key, arg in self.arguments.items():
            if arg.type != str and arg.type != list:
                continue
            val = arg.value
            if isinstance(val, list):
                val = ' '.join([str(i) for i in list])
            kw[arg.upperkey] = str(val)
        return kw

    def require_all(self):
        raise NotImplementedError  # TODO: NotImplementedError
        return self

    def use_catenate(self, arg):
        name = arg.name
        if name not in self.arguments:
            item = Argument(name, value=[])
            self.arguments.add(item)
        else:
            item = self.arguments[name]
        if is_iterable(arg.value):
            item.value.extend(list(arg.value))
        else:
            assert arg.type == str
            item.value.append(arg)
        for c in self.children:
            c.use_arg(arg)

    def check(self):
        super().check()

    def _prepare_args(self, kw):
        return kw

    def _format_cmd(self, **kw):
        s = UnusedArgFormatter().format(self.cmd, **kw)
        return s

    def _run(self):
        kw = self._process_args()
        kw = self._prepare_args(kw)
        commandstring = self._format_cmd(**kw)
        out = StringIO()
        err = StringIO()
        exit_code = run(commandstring, stdout=out, stderr=err, cwd=self._cwd)
        self.success = exit_code == 0
        if self.success:
            self.log.info(self.log.format_success() + commandstring)
        self.has_run = True
        stdout = out.getvalue()
        errout = err.getvalue()
        if stdout != '':
            out = self.log.format_info(stdout.strip())
            self.log.info(out)
        if not self.success:
            return_value_format = self.log.color('  --> ' + str(exit_code), fg='red', style='bright')
            out = errout.strip()
            if out != '':
                fatal_print = self.log.format_fail(LogStr(commandstring) + return_value_format, out)
            else:
                fatal_print = self.log.format_fail(LogStr(commandstring) + return_value_format)
            self.log.fatal(fatal_print)
        elif errout != '':
            warn_print = self.log.format_warn(LogStr(commandstring), errout.strip())
            self.log.warn(warn_print)
        self._finished(exit_code, stdout, errout)

    def __repr__(self):
        return '<class ShellTask: {0}>'.format(self.cmd)


def shell(cmd, sources=[], targets=[], always=False, cwd=None):
    return ShellTask(sources=sources, targets=targets, cmd=cmd, always=always, cwd=cwd)


def run(cmd, stdout=None, stderr=None, timeout=100, cwd=None):
    # cmd = shlex.split(cmd) # no splitting required if shell = True
    # security issue valid in our case?!
    process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd)
    output, err = process.communicate()
    exit_code = process.wait(timeout=timeout)
    if stdout is not None:
        stdout.write(output.decode('UTF-8'))
    if stderr is not None:
        stderr.write(err.decode('UTF-8'))
    return exit_code
