from .terminal import Terminal, terminal_lock
from .util import Lock
import sys


print_lock = Lock()


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
        with terminal_lock:
            self._print(term)
            if endl:
                term.newline()
            term.flush()

    def _print(self, term):
        for s in self._strings:
            if isinstance(s, LogStr):
                s._print(term)
            else:
                term.write(s, fg=self._fg, style=self._style, endl=False)

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
    """
    Povides a high level logging interface which abstracts
    away the low level formatting and printing from the
    the log messages.

    Log messages may be categorized in different log levels,
    which are ordered as follows:

        * ``fatal``: Messages which inevitably terminate the automation
            process and lead to a failure.
        * ``error``: Messages which show an error which is non-cirticl and
            can be recovered from.
        * ``warn``: Warnings should be printed on this log level (e.g. compiler
            warnings)
        * ``info``: Tools and components should print compact information on this log level.
        * ``debug``: Print as much interesting information as possible.

    The default log-level, which is shown to the user is ``warn`` (i.e. log level 3). Different
    values can be customized using config keys. For more information refer to :mod:`wasp.config`.

    :param prepend: String to be prepended to each log string.
    :param verbosity: Defines the verbosity level (log level)
    :param io: An io obect where the data should be printed to.
    :param pretty: Defines whether the logger should use pretty printing.
    """
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
        """
        Returns the currently configured verbosity level.
        """
        return self._verbosity

    @property
    def pretty(self):
        """
        Returns True if pretty printing is activated.
        """
        return self._pretty

    def color(self, s, fg=None, style=None):
        """
        Returns a LogStr initialized with given parameters.
        """
        return LogStr(s, fg=fg, style=style)

    def format_success(self, *args):
        """
        Formats a message which shows a success of some operation.
        Takes the same arguments as :fun:`wasp.format_multiline_message`.
        """
        if self._pretty:
            return self.format_multiline_message(*args, color='green', start='[SUCC]  ')
        return self.format_multiline_message(*args)

    def log_success(self, *args):
        self.info(self.format_success(*args))

    def format_fail(self, *args):
        """
        Formats a message which shows a failure of some operation.
        Takes the same arguments as :fun:`wasp.format_multiline_message`.
        """
        if self._pretty:
            return self.format_multiline_message(*args, color='red', start='[FAIL]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def log_fail(self, *args):
        self.fatal(self.format_fail(*args))

    def format_warn(self, *args):
        """
        Formats a message which shows a waring.
        Takes the same arguments as :fun:`wasp.format_multiline_message`.
        """
        if self._pretty:
            return self.format_multiline_message(*args, color='magenta', start='[WARN]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def log_warn(self, *args):
        self.warn(self.format_warn(*args))

    def format_info(self, *args):
        """
        Formats a message which delivers unstructured information to the user.
        Takes the same arguments as :fun:`wasp.format_multiline_message`.
        """
        if self._pretty:
            return self.format_multiline_message(*args, color='cyan', start='[INFO]  ', multiline='    ~~  ')
        return self.format_multiline_message(*args)

    def log_info(self, *args):
        self.info(self.format_info(*args))

    def format_multiline_message(self, *args, color=None, start='', multiline=''):
        """
        Formats a message which spans multiple lines. If the logger is configured
        with ``pretty = False``, this function only joins the args with ``\\n``.

        :param args: Tuple of :class:`LogStr` or ``str`` which each indentify a line of the output.
        :param color: Color of the prepended text.
        :param start: String to be prepended to the first line.
        :param multiline: String to be prepended to all subsequent lines.
        :return: A :class:`LogStr` with the message.
        """
        if not self.pretty:
            return '\n'.join([str(x) for x in args])
        start = self.color(start, fg=color, style='bright')
        if len(args) > 0:
            first = True
            new_args = []
            ret = None
            for arg in args:
                if isinstance(arg, LogStr):
                    new_args.append(arg)
                    continue
                assert isinstance(arg, str)
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
        """
        Write a message to the log.

        :param msg: The message to be printed. Either of type ``str`` or :class:`LogStr`.
        :param level: log level in which the message should be printed. Expects ``int``.
        :param stderr: Defines whether the message should be printed to stderr.
        """
        if level > self._verbosity:
            return
        msg = LogStr(self._prepend, msg)
        str_msg = str(msg)
        if self._io is not None:
            self._io.write(str_msg + '\n')
        if not stderr:
            if sys.stdout.isatty():
                msg.write_to_terminal(endl=True)
            else:
                with print_lock:
                    print(str_msg)
        else:
            if sys.stderr.isatty():
                msg.write_to_terminal(endl=True, term=Terminal(file=sys.stderr))
            else:
                with print_lock:
                    print(str_msg, file=sys.stderr)

    def configure(self, verbosity=None, pretty=None):
        """
        Configures the :class:`Logger`.

        :param verbosity: Defines the verbosity level (log level).
        :param pretty: Defines whether pretty printing is activated or not.
        """
        if verbosity is not None:
            self._verbosity = verbosity
        if pretty is not None:
            self._pretty = pretty
        return self

    def fatal(self, msg, stderr=True):
        """
        Prints the message with log level ``fatal``.
        """
        self.log(msg, level=self.FATAL, stderr=stderr)

    def error(self, msg, stderr=True):
        """
        Prints the message with log level ``error``.
        """
        self.log(msg, level=self.ERROR, stderr=stderr)

    def warn(self, msg, stderr=True):
        """
        Prints the message with log level ``warn``.
        """
        self.log(msg, level=self.WARN, stderr=stderr)

    def info(self, msg, stderr=False):
        """
        Prints the message with log level ``info``.
        """
        self.log(msg, level=self.INFO, stderr=stderr)

    def debug(self, msg, stderr=False):
        """
        Prints the message with log level ``debug``.
        """
        self.log(msg, level=self.DEBUG, stderr=stderr)

    def clone(self):
        """
        Clones this logger and returns a new Logger with the
        same configuration.
        """
        # TODO: ensure that io is thread save
        return Logger(prepend=str(self._prepend), verbosity=self._verbosity, io=self._io, pretty=self._pretty)