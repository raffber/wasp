import os
import sys
from .task import Task
from .node import FileNode
from .argument import find_argumentkeys_in_string
from .util import UnusedArgFormatter
from .logging import LogStr
from .fs import Directory, top_dir, Path
from . import ctx, osinfo

from subprocess import Popen, PIPE
import shlex
from time import sleep

POLL_TIMEOUT = 0.05  # s

INVALID_ENV_ARGUMENT = 'Argument `env` for shell must be in the format of ' \
                       '{"name": "value"} or {"name": ["list", "of", "values"]}'


class ShellTask(Task):
    """
    Task for running commands on the shell. It provides the following features:

        * Setting a command (using the ``cmd`` field) and injecting source and target values into it.
        * Automatic formatting of the command to be executed.
        * Setting the working directory from which the command should be executed.
        * Specially formatted logging (depending on whether pretty printing is activated)

    :param sources: Source nodes consumed by the task.
    :param targets: Target nodes produced by the task.
    :param cmd: Command string. May also be set by overriding the ``cmd`` attribute.
    :param always: Determines whether the task should be executed regardless of whether targets
        or sources have changed.
    :param cwd: Set the working directory from which the shell command should be run.
    """
    def __init__(self, sources=[], targets=[], cmd='', always=False, cwd=None):
        self._cmd = cmd
        self._printer = None
        if cwd is None:
            self._cwd = top_dir()
        else:
            self._cwd = Directory(cwd, make_absolute=True).path
        self._out = None
        super().__init__(sources=sources, targets=targets, always=always)

    @property
    def out(self):
        """
        Returns the output of the shell command as :class:`ProcessOut`.
        """
        return self._out

    @property
    def cwd(self):
        """
        Returns the working directory where the shell command should be executed.
        """
        return self._cwd

    @property
    def cmd(self):
        """
        Returns the shell command to be executed.
        """
        return self._cmd

    def _finished(self, exit_code, out, err):
        """
        Called when the shell command has finished running. May be overridden
        to implement special error handling of the output. Must set the
        ``self.success``. (default implementation: ``self.success = exit_code == 0``)
        """
        self.success = exit_code == 0

    def _process_args(self):
        """
        Creates a dict of {'key': 'value'} to be used for formatting the command string.
        For example '{CC} {CFLAGS} {SRC}` contains the keys 'CC', 'CFLAGS' and 'SRC', which
        can be injected using the values in the dict returned by this function. E.g. returning
        {'CC': 'gcc', 'SRC': 'main.c'} would result in 'gcc main.c' being executed.
        By default, this function injects 'SRC' with a list of all sources and 'TGT' with
        a list of all targets. Additionally each used argument is accessible by its key as well.
        (in lowercase as well as in uppercase).
        """
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
        src_str = ' '.join([quote(x) for x in src_list])
        tgt_str = ' '.join([quote(x) for x in tgt_list])
        kw = {'SRC': src_str,
              'src': src_str,
              'TGT': tgt_str,
              'tgt': tgt_str}
        # assign upper and lower keys, s.t. it is up to the preference of
        # users how to format command strings.
        # typically, one uses upper case variable names, however, people
        # who have not grown up with make, will probably use the less shouty version
        # and use lower-case strings.
        for key, arg in self.arguments.items():
            if isinstance(arg.value, Path):
                value = arg.value.path
            elif arg.type != str:
                continue
            else:
                value = arg.value
            if '-' in key:
                key = key.replace('-', '_')
            value = quote(str(value))
            kw[key.upper()] = value
            kw[key.lower()] = value
        return kw

    def require_all(self):
        """
        Automatically calls ``self.require()`` on all keys in ``self.cmd``.
        """
        for argname in find_argumentkeys_in_string(self.cmd):
            self.require(argname)
        return self

    def _format_cmd(self):
        """
        Formats ``self.cmd`` into an executable string by calling
        ``self._prcess_args()``.
        """
        kw = self._process_args()
        s = UnusedArgFormatter().format(self.cmd, **kw)
        post_format_repl = {
            'BUILDDIR': str(ctx.builddir),
            'builddir': str(ctx.builddir),
            'TOPDIR': str(ctx.topdir),
            'topdir': str(ctx.topdir)
        }
        return UnusedArgFormatter().format(s, **post_format_repl)

    def _make_env(self):
        envarg = self.arguments.value('env', default=None)
        if envarg is None:
            return os.environ
        if self.arguments.value('clearenv', False):
            env = {}
        else:
            env = dict(os.environ.copy().items())
        assert isinstance(envarg, dict), INVALID_ENV_ARGUMENT
        for k, v in envarg.items():
            assert isinstance(k, str) and (isinstance(v, list) or isinstance(v, str)), INVALID_ENV_ARGUMENT
            if isinstance(v, list):
                v = os.pathsep.join(v)
            env[k] = v
        return env

    def _run(self):
        """
        Formats, executes the shell command and postprocesses its output.
        """
        commandstring = self._format_cmd()
        exit_code, out = run(commandstring, cwd=self._cwd, print=not self.log.pretty, env=self._make_env())
        self._out = out
        self._finished(exit_code, out.stdout, out.stderr)
        if self.success:
            self.log.info(self.log.format_success() + commandstring)
        self.printer.print(self.success, stdout=out.stdout, stderr=out.stderr,
                           exit_code=exit_code, commandstring=commandstring)

    def use_arg(self, arg):
        if arg.name == 'env':
            curarg = self.arguments.get('env')
            if curarg is None:
                super().use_arg(arg)
                return
            assert arg.type == dict, INVALID_ENV_ARGUMENT
            assert curarg.type == dict, INVALID_ENV_ARGUMENT
            for k, v in arg.value.items():
                assert isinstance(k, str), INVALID_ENV_ARGUMENT
                assert isinstance(v, list) or isinstance(v, str), INVALID_ENV_ARGUMENT
                curval = curarg.value[k]
                assert isinstance(curval, list) or isinstance(curval, str), INVALID_ENV_ARGUMENT
                if not isinstance(curval, list):
                    curval = [curval]
                if not isinstance(v, list):
                    v = [v]
                curval.extend(v)
                curarg.value[k] = v
            return
        super().use_arg(arg)

    def __repr__(self):
        return '<class ShellTask: {0}>'.format(self.cmd)

    def get_printer(self):
        if self._printer is None:
            self._printer = ShellTaskPrinter(self)
        return self._printer

    def set_printer(self, printer):
        self._printer = printer

    printer = property(get_printer, set_printer)
    """
    Returns a :class:`ShellTaskPrinter` object used for printing the output
    of the shell command.
    """


class ShellTaskPrinter(object):
    """
    Creates a printer object for a :class:`ShellTask`.
    """

    def __init__(self, task):
        self._task = task

    def print(self, success, stdout='', stderr='', exit_code=0, commandstring=''):
        """
        Called after the execution of the shell task has finished.

        :param success: True if the task finished successfully.
        :param stdout: The string which was printed to ``stdout``.
        :param stderr: The string which was printed to ``stderr``.
        :param exit_code: The exit code of the process.
        :param commandstring: The command that was executed.
        """
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
    """
    Equivalent to ``ShellTask(...)``.
    """
    return ShellTask(sources=sources, targets=targets, cmd=cmd, always=always, cwd=cwd)


class ProcessOut(object):
    """
    Storage object for returning the ouptput (stdout and stderr) of
    a task.

    :param print: If True, everything written to ``write()`` is directly printed
        to stdout or stderr.
    """
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
        """
        Store a message in this object.

        :param msg: Message as str.
        :param stdout: True if the message belongs to stdout, False otherwise (stderr).
        """
        if stdout:
            self._out.append((msg, self.OUT))
        else:
            self._out.append((msg, self.ERR))
        if self._print and stdout:
            print(msg, file=sys.stdout)
            sys.stdout.flush()
        elif self._print:
            print(msg, file=sys.stderr)
            sys.stderr.flush()

    def finished(self):
        """
        Called if the shell process has finished executing.
        """
        self._finished = True

    @property
    def stdout(self):
        """
        Returnt the ``stdout`` output of the process as string.
        """
        if self._finished and self._stdout_cache is not None:
            return self._stdout_cache
        self._stdout_cache = '\n'.join(filter(lambda x: x is not None, [x if tp == self.OUT else None for x, tp in self._out]))
        return self._stdout_cache

    @property
    def stderr(self):
        """
        Returnt the ``stderr`` output of the process as string.
        """
        if self._finished and self._stderr_cache is not None:
            return self._stderr_cache
        self._stderr_cache = '\n'.join(filter(lambda x: x is not None, [x if tp == self.ERR else None for x, tp in self._out]))
        return self._stderr_cache

    @property
    def merged(self):
        """
        Returnt the ``stdout`` and ``stderr`` output of the process merged into one string.
        """
        if self._finished and self._merged_cache is not None:
            return self._merged_cache
        self._merged_cache = '\n'.join(x for x, tp in self._out)
        return self._merged_cache


def run(cmd, timeout=100, cwd=None, print=False, env=None):
    """
    Executes a command ``cmd`` with the given ``timeout``.

    :param cmd: The command to be executed.
    :param timeout: The maximum time the command can take before it is interrupted.
    :param cwd: The working directory from which the command should be executed.
    :param print: Determines if the output of the command should be printed directly to
        stderr and stdout.
    :return: Tuple of ``exit_code`` and :class:`ProcessOut`.
    """
    exit_code = None
    out = ProcessOut(print=print)
    try:
        process = Popen(cmd, stdout=PIPE, stderr=PIPE,
                        shell=True, cwd=cwd, universal_newlines=True, env=env)
        # XXX: this is some proper hack, but it is quite unavoidable
        # maybe use different library?!
        time_running = 0
        while process.poll() is None:
            time_running += POLL_TIMEOUT
            sleep(POLL_TIMEOUT)  # poll interval is 50ms
            if time_running >= timeout:
                raise TimeoutError
            for line in process.stdout:
                out.write(line.strip('\n'), stdout=True)
            for line in process.stderr:
                out.write(line.strip('\n'), stdout=False)
        out.finished()
        exit_code = process.returncode
    except TimeoutError:
        pass
    return exit_code, out


def quote(s):
    """
    Ensures that a shell command is properly quoted.
    Equivalent to ``shlex.quote``.
    """
    if not isinstance(s, str):
        s = str(s)
    # http://blogs.msdn.com/b/twistylittlepassagesallalike/archive/2011/04/23/everyone-quotes-arguments-the-wrong-way.aspx
    if osinfo.windows:
        # XXX this is huge hack and it will not work in many cases..
        # but why does shlex.quote() use single quotes on windows as well?
        # somehow escape for cmd.exe (this causes issues with program to invoke)
        return '"' + s + '"'
    return shlex.quote(s)
