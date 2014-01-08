import os


class WaspDirectory(object):
    def __init__(self, pathname):
        if not os.isdir(pathname):
            raise FileNotFoundError('No such directory: {0}'.format(pathname))
        self.pathname = pathname
