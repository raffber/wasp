import os


class WaspDirectory(object):
    def __init__(self, path):
        if not os.isdir(path):
            raise FileNotFoundError('No such directory: {0}'.format(path))
        self._path = path

    def join(self, *args):
        return os.path.join(self.path, *args)

    @property
    def path(self):
        return self._path

    def ensure_exists(self):
        pass