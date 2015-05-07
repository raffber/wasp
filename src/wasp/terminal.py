from . import osinfo


class Color:
    default = None
    red = 'red'
    blue = 'blue'
    yellow = 'yellow'
    black = 'black'
    white = 'white'
    green = 'green'
    cyan = 'cyan'
    magenta = 'magenta'


class Style(object):
    normal = None
    dim = 'dim'
    bright = 'bright'


class Cursor(object):
    def up(self, n=1):
        pass

    def down(self, n=1):
        pass

    def left(self, n=1):
        pass

    def right(self, n=1):
        pass

    def to_pos(self, x, y):
        pass


class Terminal(object):

    def __init__(self):
        self._cursor = Cursor()

    def set_title(self, title):
        pass

    @property
    def cursor(self):
        return self._cursor

    @property
    def width(self):
        return -1

    @property
    def height(self):
        return -1

    def newline(self):
        print()

    # noinspection PyUnusedLocal
    def write(self, s, fg=Color.default, bg=Color.default, style=Style.normal, endl=True):
        print(s)


if osinfo.windows:
    from .terminal_win import Terminal, Cursor
elif osinfo.posix:
    from .terminal_ansi import Terminal, Cursor
else:
    print('Unrecognized platform! Terminal coloring unsupported!')