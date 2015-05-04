from platform import system


class OSInfo(object):
    """
    Object for gathering information about the current platform.
    """

    def __init__(self):
        self._name = system()

    def name(self):
        """
        Returns the system name.
        """
        return self._name

    @property
    def posix(self):
        """
        Returns True if the operating system is (at least mostly) POSIX compliant.
        """
        return self._name == 'Linux' or self._name == 'Darwin'

    @property
    def windows(self):
        """
        Returns True if the current OS is Windows.
        """
        return self._name == 'Windows'

    @property
    def linux(self):
        """
        Returns True if the current OS is Linux.
        """
        return self._name == 'Linux'

    @property
    def osx(self):
        """
        Returns True if the current OS is Apples OSX.
        """
        return self._name == 'Darwin'