from .terminal import Terminal
import sys


class LogStr(object):
    def __init__(self, *strs, fg=None, style=None):
        self._strings = list(strs)
        self._fg = fg
        self._style = style

    def __str__(self):
        return self.to_string()

    def to_string(self):
        ret = ''
        for s in self._strings:
            ret += str(s)
        return ret

    def write_to_terminal(self, term=None, endl=False):
        if term is None:
            term = Terminal()
        for s in self._strings:
            if isinstance(s, LogStr):
                s.write_to_terminal(term)
            else:
                term.write(s, fg=self._fg, style=self._style, endl=False)
        if endl:
            term.newline()

    def __add__(self, other):
        self._strings.append(other)


def color(s, fg=None, style=None):
    return LogStr(s, fg=fg, style=style)


class Logger(object):
    QUIET = 0
    FATAL = 1
    ERROR = 2
    WARN = 3
    INFO = 4
    DEBUG = 5

    DEFAULT = 3

    def __init__(self, prepend='', verbosity=DEFAULT, use_stdout=True, io=None):
        self._use_stdout = use_stdout
        self._verbosity = verbosity
        self._io = io
        self._prepend = prepend

    @property
    def verbosity(self):
        return self._verbosity

    def log(self, msg, level=None):
        if level > self._verbosity:
            return
        msg = LogStr(self._prepend, msg)
        str_msg = str(msg)
        if self._io is not None:
            self._io.write(str_msg)
        if self._use_stdout and sys.stdout.isatty():
            msg.write_to_terminal(endl=True)
        else:
            print(str_msg)

    def configure(self, verbosity):
        self._verbosity = verbosity

    def fatal(self, msg):
        self.log(msg, level=self.FATAL)

    def error(self, msg):
        self.log(msg, level=self.ERROR)

    def warn(self,  msg):
        self.log(msg, level=self.WARN)

    def info(self,  msg):
        self.log(msg, level=self.INFO)

    def debug(self,  msg):
        self.log(msg, level=self.DEBUG)

    def clone(self):
        # TODO: ensure that io is thread save
        return Logger(prepend=str(self._prepend), verbosity=self._verbosity
                      , use_stdout=self._use_stdout, io=self._io)