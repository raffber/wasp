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
        """
        Moves the cursor up by ``n`` lines.
        """
        pass

    def down(self, n=1):
        """
        Moves the cursor down by ``n`` lines.
        """
        pass

    def left(self, n=1):
        """
        Moves the cursor left by ``n`` columns.
        """
        pass

    def right(self, n=1):
        """
        Moves the cursor right by ``n`` columns.
        """
        pass

    def to_pos(self, x, y):
        """
        Moves the cursor to a specific position
        """
        pass


class Terminal(object):
    """
    Class abstracting a basic terminal interface, which
    supports moving the cursor, setting titles and
    returning the dimension of the terminal window.
    """

    def __init__(self):
        self._cursor = Cursor()

    def set_title(self, title):
        """
        Sets the title of the terminal to ``title``.
        """
        pass

    @property
    def cursor(self):
        """
        Returns a subclass of :class:`Cursor` which allows
        setting modifying the cursor position.
        """
        return self._cursor

    @property
    def width(self):
        """
        Returns the width of the terminal window. -1 if unsupported.
        """
        return -1

    @property
    def height(self):
        """
        Returns the height of the terminal window. -1 if unsupported.
        """
        return -1

    def newline(self):
        """
        Prints a newline to the terminal.
        """
        print()

    # noinspection PyUnusedLocal
    def write(self, s, fg=Color.default, bg=Color.default, style=Style.normal, endl=True):
        print(s)


# conditional imports based on operating system
if osinfo.windows:
    from .terminal_win import Terminal, Cursor
elif osinfo.posix:
    from .terminal_ansi import Terminal, Cursor
else:
    print('Unrecognized platform! Terminal coloring unsupported!')