
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

def require_version(self, *args):
    major = minor = point = -1
    if len(args) >= 1:
        major = args[0] 
    if len(args) >= 2:
        minor = args[1]
    if len(args) >= 3:
        point = args[2]
    VERSION.is_compatible(major, minor, point)

