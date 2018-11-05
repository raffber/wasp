from .terminal import Color, Style
import os
import sys
from .util import Lock


# escape codes
CSI = '\033['
OSC = '\033]'
BEL = '\007'


# foreground color codes
fgcolor_to_code = {
    None: 39,
    'black': 30,
    'red': 31,
    'green': 32,
    'yellow': 33,
    'blue': 34,
    'magenta': 35,
    'cyan': 36,
    'white': 37
}

# background color codes
bgcolor_to_code = {
    None: 49,
    'black': 40,
    'red': 41,
    'green': 42,
    'yellow': 43,
    'blue': 44,
    'magenta': 45,
    'cyan': 46,
    'white': 47
}

# style color codes
style_to_code = {
    None: 22,
    'bright': 1,
    'dim': 2
}


def code(arg):
    return CSI + str(arg) + 'm'


class Cursor(object):
    def __init__(self, term):
        self._term = term

    def up(self, num=1):
        assert num > 0
        self._term.print_noendl(CSI + str(num) + 'A')

    def down(self, num=1):
        assert num > 0
        self._term.print_noendl(CSI + str(num) + 'B')

    def right(self, num=1):
        assert num > 0
        self._term.print_noendl(CSI + str(num) + 'C')

    def left(self, num=1):
        assert num > 0
        self._term.print_noendl(CSI + str(num) + 'D')

    def to_pos(self, x, y):
        assert x > 0 and y > 0
        self._term.print_noendl(CSI + str(y) + ';' + str(x) + 'H')


terminal_lock = Lock()


class Terminal(object):
    def __init__(self, file=None):
        if file is None:
            self._file = sys.stdout
        else:
            self._file = file
        self._cursor = Cursor(self)

    @property
    def cursor(self):
        return self._cursor

    def set_title(self, title):
        self.print_noendl(OSC + '2;' + title + BEL)

    @property
    def width(self):
        try:
            cols = os.environ('COLUMNS')
        except KeyError:
            return -1
        try:
            return int(cols)
        except ValueError:
            return -1

    @property
    def height(self):
        try:
            cols = os.environ('LINES')
        except KeyError:
            return -1
        try:
            return int(cols)
        except ValueError:
            return -1

    def write(self, s, fg=Color.default, bg=Color.default, style=Style.normal, endl=True):
        start = (code(fgcolor_to_code[fg]) +
                 code(bgcolor_to_code[bg]) +
                 code(style_to_code[style]))
        stop = (code(fgcolor_to_code[Color.default]) +
                code(bgcolor_to_code[Color.default]) +
                code(style_to_code[Style.normal]))
        if endl:
            self.print(start + s + stop)
        else:
            self.print_noendl(start + s + stop)

    def print_noendl(self, s):
        print(s, end='', flush=True, file=self._file)

    def print(self, s):
        print(s, file=self._file)

    def clear_screen(self):
        self.print_noendl(CSI + '2J')

    def clear_line(self):
        self.print_noendl(CSI + '2K')

    def newline(self):
        print(file=self._file)

    def flush(self):
        self._file.flush()
