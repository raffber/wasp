

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
        msg = self._prepend + msg
        if self._io is not None:
            self._io.write(msg)
        if self._use_stdout:
            print(msg)

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