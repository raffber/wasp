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