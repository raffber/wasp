from .task import Task
from .node import FileNode
from .argument import Argument
from .util import UnusedArgFormatter, is_iterable
from .logging import LogStr
from io import StringIO
from subprocess import Popen, PIPE


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd='', always=False):
        super().__init__(sources=sources, targets=targets, children=children, always=always)
        self._cmd = cmd

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
        exit_code = run(commandstring, stdout=out, stderr=err)
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
            fatal_print = self.log.format_fail(LogStr(commandstring) + return_value_format, errout.strip())
            self.log.fatal(fatal_print)
        elif errout != '':
            warn_print = self.log.format_warn(LogStr(commandstring), errout.strip())
            self.log.warn(warn_print)
        self._finished(exit_code, stdout, errout)

    def __repr__(self):
        return '<class ShellTask: {0}>'.format(self.cmd)


def shell(cmd, sources=[], targets=[], always=False):
    return ShellTask(sources=sources, targets=targets, cmd=cmd, always=always)


def run(cmd, stdout=None, stderr=None, timeout=100):
    # cmd = shlex.split(cmd) # no splitting required if shell = True
    process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
    output, err = process.communicate()
    exit_code = process.wait(timeout=timeout)
    if stdout is not None:
        stdout.write(output.decode('UTF-8'))
    if stderr is not None:
        stderr.write(err.decode('UTF-8'))
    return exit_code
