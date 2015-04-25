from .terminal import Terminal
import sys


class LogStr(object):
    """
    Annotates strings with a style set and color for printing them
    to a terminal (which supports colors).

    :param strs: Tuple of strings or :class:`LogStr` which are to be printed.
    :param fg: Foreground color. See :class:`wasp.terminal.Color` for more information.
    :param style: Text style. see :class:`wasp.terminal.Style` for more information.
    """
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
        """
        Writes the string to a terminal.

        :param term: Terminal to be written to. If None, a new terminal is created.
        :param endl: Determines whether a newline should be appended after printing.
        """
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
        """
        Returns a new LogStr which is a concatenation of self and other.
        """
        return LogStr(self, other)

    def __iadd__(self, other):
        """
        Appends other to self.
        """
        self._strings.append(other)
        return self


class Logger(object):
    QUIET = 0
    FATAL = 1
    ERROR = 2
    WARN = 3
    INFO = 4
    DEBUG = 5

    DEFAULT = 3

    def __init__(self, prepend='', verbosity=DEFAULT, io=None, pretty=True):
        self._verbosity = verbosity
        self._io = io
        self._prepend = prepend
        self._pretty = pretty

    @property
    def verbosity(self):
        return self._verbosity

    @property
    def pretty(self):
        return self._pretty

    def color(self, s, fg=None, style=None):
        return LogStr(s, fg=fg, style=style)

    def format_success(self, *args):
        if self._pretty:
            return self.format_multiline_message(*args, color='green', start='[SUCC]  ')
        return self.format_multiline_message(*args)

    def format_fail(self, *args):
        if self._pretty:
            return self.format_multiline_message(*args, color='red', start='[FAIL]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def format_warn(self, *args):
        if self._pretty:
            return self.format_multiline_message(*args, color='magenta', start='[WARN]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def format_info(self, *args):
        if self._pretty:
            return self.format_multiline_message(*args, color='cyan', start='[INFO]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def format_multiline_message(self, *args, color=None, start='', multiline=''):
        start = self.color(start, fg=color, style='bright')
        if len(args) > 0:
            first = True
            new_args = []
            ret = None
            for arg in args:
                if isinstance(arg, LogStr):
                    new_args.append(arg)
                    continue
                new_args.extend(arg.split('\n'))
            for arg in new_args:
                if first:
                    ret = start + arg
                    first = False
                    continue
                ret += '\n'
                ret += self.color(multiline, fg=color, style='bright') + arg
            return ret
        return start

    def log(self, msg, level=None, stderr=False):
        if level > self._verbosity:
            return
        msg = LogStr(self._prepend, msg)
        str_msg = str(msg)
        if self._io is not None:
            self._io.write(str_msg)
        if not stderr:
            if sys.stdout.isatty():
                msg.write_to_terminal(endl=True)
            else:
                print(str_msg)
        else:
            if sys.stderr.isatty():
                msg.write_to_terminal(endl=True, term=Terminal(file=sys.stderr))
            else:
                print(str_msg, file=sys.stderr)

    def configure(self, verbosity=None, pretty=None):
        if verbosity is not None:
            self._verbosity = verbosity
        if pretty is not None:
            self._pretty = pretty

    def fatal(self, msg, stderr=True):
        self.log(msg, level=self.FATAL, stderr=stderr)

    def error(self, msg, stderr=True):
        self.log(msg, level=self.ERROR, stderr=stderr)

    def warn(self, msg, stderr=True):
        self.log(msg, level=self.WARN, stderr=stderr)

    def info(self, msg, stderr=False):
        self.log(msg, level=self.INFO, stderr=stderr)

    def debug(self, msg, stderr=False):
        self.log(msg, level=self.DEBUG, stderr=stderr)

    def clone(self):
        # TODO: ensure that io is thread save
        return Logger(prepend=str(self._prepend), verbosity=self._verbosity, io=self._io, pretty=self._pretty)