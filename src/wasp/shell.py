from .task import Task
from .node import FileNode
from .argument import Argument, find_argumentkeys_in_string
from .util import UnusedArgFormatter, is_iterable
from .logging import LogStr
from .fs import Directory

from io import StringIO
from subprocess import Popen, PIPE, STDOUT
import shlex


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd='', always=False, cwd=None):
        super().__init__(sources=sources, targets=targets, children=children, always=always)
        self._cmd = cmd
        self._printer = None
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
                src_path = s.to_file().relative(self._cwd, skip_if_abs=True).path
                src_list.append(src_path)
        tgt_list = []
        for t in self.targets:
            if isinstance(t, FileNode):
                tgt_path = t.to_file().relative(self._cwd, skip_if_abs=True).path
                tgt_list.append(tgt_path)
        src_str = ' '.join(src_list)
        tgt_str = ' '.join(tgt_list)
        kw = {'SRC': src_str,
              'TGT': tgt_str}
        for key, arg in self.arguments.items():
            if arg.type != str and arg.type != list:
                continue
            val = arg.value
            if is_iterable(val):
                val = ' '.join([str(i) for i in list])
            kw[arg.upperkey] = str(val)
        # assign upper and lower keys, s.t. it is up to the preference of
        # users how to format command strings.
        # typically, one uses upper case variable names, however, people
        # who have not grown up with make, will probably use the less shouty version
        # and use lower-case strings.
        kw_new = {}
        for k, v in kw.items():
            kw_new[k] = v
            kw_new[k.lower()] = v
        return kw_new

    def require_all(self):
        for argname in find_argumentkeys_in_string(self.cmd):
            self.require(argname)
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

    def _format_cmd(self):
        kw = self._process_args()
        s = UnusedArgFormatter().format(self.cmd, **kw)
        return s

    def _run(self):
        commandstring = self._format_cmd()
        out = StringIO()
        err = StringIO()
        if self.log.pretty:
            exit_code = run(commandstring, stdout=out, stderr=err, cwd=self._cwd)
        else:
            exit_code = run(commandstring, stdout=out, stderr=err, cwd=self._cwd, forward_stderr=True)
        stdout = out.getvalue()
        stderr = err.getvalue()
        self._finished(exit_code, stdout, stderr)
        if self.success:
            self.log.info(self.log.format_success() + commandstring)
        self.has_run = True
        self.printer.print(self.success, stdout=stdout, stderr=stderr,
                           exit_code=exit_code, commandstring=commandstring)

    def __repr__(self):
        return '<class ShellTask: {0}>'.format(self.cmd)

    def get_printer(self):
        if self._printer is None:
            self._printer = ShellTaskPrinter(self)
        return self._printer

    def set_printer(self, printer):
        self._printer = printer

    printer = property(get_printer, set_printer)


class ShellTaskPrinter(object):

    def __init__(self, task):
        self._task = task

    def print(self, success, stdout='', stderr='', exit_code=0, commandstring=''):
        log = self._task.log
        if not success:
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
        if stdout != '':
            out = log.format_info(stdout.strip())
            log.info(out)


def shell(cmd, sources=[], targets=[], always=False, cwd=None):
    return ShellTask(sources=sources, targets=targets, cmd=cmd, always=always, cwd=cwd)


def run(cmd, stdout=None, stderr=None, timeout=100, cwd=None, forward_stderr=False):
    exit_code = None
    try:
        if forward_stderr:
            process = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True, cwd=cwd)
        else:
            process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd)
        exit_code = process.wait(timeout=timeout)
        output, err = process.communicate()
        if stdout is not None:
            stdout.write(output.decode('UTF-8'))
        if stderr is not None and not forward_stderr:
            stderr.write(err.decode('UTF-8'))
    except TimeoutError:
        pass
    return exit_code


def quote(s):
    return shlex.quote(s)