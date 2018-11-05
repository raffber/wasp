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


if osinfo.windows:
    from .terminal_win import Terminal, Cursor, terminal_lock
elif osinfo.posix:
    from .terminal_ansi import Terminal, Cursor, terminal_lock
