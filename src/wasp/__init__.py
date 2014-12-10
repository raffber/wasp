from .util import Proxy
ctx = Proxy('The wasp context wasp.ctx can only be accessed after initialization.')


class WaspVersion(object):
    def __init__(self, major, minor, point):
        self.major = major
        self.minor = minor
        self.point = point

    def is_compatible(self, major, minor, point):
        if major == -1:
            return True
        if major != self.major:
            return False
        if minor == -1:
            return True
        if minor != self.minor:
            return False
        if point == -1:
            return True
        if point != self.point:
            return False


VERSION = WaspVersion(0, 1, 0)


def require_version(*args):
    major = minor = point = -1
    if len(args) >= 1:
        major = args[0] 
    if len(args) >= 2:
        minor = args[1]
    if len(args) >= 3:
        point = args[2]
    VERSION.is_compatible(major, minor, point)


from .util import Factory, Serializable
factory = Factory()

from .signature import SignatureProvider, SignatureStore
signatures = SignatureProvider()
old_signatures = SignatureStore()


def recurse(*fpaths):
    import os
    for f in fpaths:
        if isinstance(f, list):
            recurse(*f)
            continue
        assert isinstance(f, str), 'Arguments to recurse() must be strings or ' \
                                   'lists thereof. Found {0}'.format(type(f).__name__)
        if not os.path.isdir(f):
            f = os.path.dirname(f)
        recurse_files.append(f)

recurse_files = []

from .context import Context
from .options import options
from .argument import Argument,  MissingArgumentError
from .command import build, configure, install, command
from .hooks import init, create_context
from .fs import Directory, File
from .generator import generate
from .task import Task, group
from .shell import shell
from .fs import Directory, TOP_DIR, file, files
from .tools import tool


