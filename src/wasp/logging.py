

class Logger(object):
    FATAL = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4

    def __init__(self, prepend='', verbosity=0, use_stdout=True, io=None):
        self._use_stdout = use_stdout
        self._verbosity = verbosity
        self._io = io
        self._prepend = prepend

    def log(self, msg, level=None):
        if level < self._verbosity:
            return
        msg = self._prepend + msg
        if self._io is not None:
            self._io.write(msg)
        if self._use_stdout:
            print(msg)

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