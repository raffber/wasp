from platform import system


class OSInfo(object):

    def __init__(self):
        self._name = system()

    def name(self):
        return self._name

    @property
    def posix(self):
        return self._name == 'Linux' or self._name == 'Darwin'

    @property
    def windows(self):
        return self._name == 'Windows'

    @property
    def linux(self):
        return self._name == 'Linux'

    @property
    def osx(self):
        return self._name == 'Darwin'