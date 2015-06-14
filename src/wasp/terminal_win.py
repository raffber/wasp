import sys
from .terminal import Color


class Cursor(object):
    def __init__(self, term):
        self._term = term

    def up(self, num=1):
        pass

    def down(self, num=1):
        pass

    def right(self, num=1):
        pass

    def left(self, num=1):
        pass

    def to_pos(self, x, y):
        pass


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
        pass

    @property
    def width(self):
        return -1

    @property
    def height(self):
        return -1

    def write(self, s, fg=Color.default, bg=Color.default, style=Style.normal, endl=True):
        if endl:
            self.print(s)
        else:
            self.print_noendl(s)

    def print_noendl(self, s):
        print(s, end='', flush=True, file=self._file)

    def print(self, s):
        print(s, file=self._file)

    def clear_screen(self):
        pass

    def clear_line(self):
        pass

    def newline(self):
        print(file=self._file)
