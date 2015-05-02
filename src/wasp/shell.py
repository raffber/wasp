import sys
from .task import Task
from .node import FileNode
from .argument import Argument, find_argumentkeys_in_string
from .util import UnusedArgFormatter, is_iterable
from .logging import LogStr
from .fs import Directory

from subprocess import Popen, PIPE
import shlex
from time import sleep

POLL_TIMEOUT = 0.05  # s


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd='', always=False, cwd=None):
        super().__init__(sources=sources, targets=targets, children=children, always=always)
        self._cmd = cmd
        self._printer = None
        if cwd is None:
            self._cwd = None
        else:
            self._cwd = Directory(cwd, make_absolute=True).path
        self._out = None

    @property
    def out(self):
        return self._out

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
            if '-' in k:
                k = k.replace('-', '_')
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
        exit_code, out = run(commandstring, cwd=self._cwd, print=not self.log.pretty)
        self._out = out
        self._finished(exit_code, out.stdout, out.stderr)
        if self.success:
            self.log.info(self.log.format_success() + commandstring)
        self.printer.print(self.success, stdout=out.stdout, stderr=out.stderr,
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


class ProcessOut(object):
    ERR = 1
    OUT = 0

    def __init__(self, print=False):
        self._out = []
        self._stdout_cache = None
        self._stderr_cache = None
        self._merged_cache = None
        self._finished = False
        self._print = print

    def write(self, msg, stdout=True):
        if stdout:
            self._out.append((msg, self.OUT))
        else:
            self._out.append((msg, self.ERR))
        if self._print and stdout:
            print(msg, file=sys.stdout)
        elif self._print:
            print(msg, file=sys.stderr)

    def finished(self):
        self._finished = True

    @property
    def stdout(self):
        if self._finished and self._stdout_cache is not None:
            return self._stdout_cache
        self._stdout_cache = '\n'.join(filter(lambda x: x is not None, [x if tp == self.OUT else None for x, tp in self._out]))
        return self._stdout_cache

    @property
    def stderr(self):
        if self._finished and self._stderr_cache is not None:
            return self._stderr_cache
        self._stderr_cache = '\n'.join(filter(lambda x: x is not None, [x if tp == self.ERR else None for x, tp in self._out]))
        return self._stderr_cache

    @property
    def merged(self):
        if self._finished and self._merged_cache is not None:
            return self._merged_cache
        self._merged_cache = '\n'.join(x for x, tp in self._out)
        return self._merged_cache


def run(cmd, timeout=100, cwd=None, print=False):
    exit_code = None
    out = ProcessOut(print=print)
    try:
        process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=cwd, universal_newlines=True)
        # XXX: this is some proper hack, but it is quite unavoidable
        # maybe use different library?!
        time_running = 0
        while process.poll() is None:
            time_running += POLL_TIMEOUT
            sleep(POLL_TIMEOUT)  # poll interval is 50ms
            if time_running >= timeout:
                raise TimeoutError
            stdout = process.stdout.read()
            if len(stdout) != 0:
                out.write(stdout, stdout=True)
            stderr = process.stderr.read()
            if len(stderr) != 0:
                out.write(stderr, stdout=False)
        out.finished()
        exit_code = process.returncode
    except TimeoutError:
        pass
    return exit_code, out


def quote(s):
    return shlex.quote(s)
