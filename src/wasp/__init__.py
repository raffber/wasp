"""
This is the main module of wasp. It imports commonly used symbols
into its namespace and defines all global variables. At the momemnt, these are:

 * decorators: Acts as a central storage for storing functions registered
   using decorators
 * ctx: Captures the state of the application, such as the top-directory and signatures of files.
 * osinfo: Allows retrieving information about the operating system
   the application is running on.
 * version: Defines the version of the application.
 * log: The logger for the application.
 * factory: A factory for producing types which inherits from Serializable.
   During module import, they must be registered.
 * extensions: A collection of registered extensions.
 * _recurse_files: A list of files which have been registered by :func:`recurse`
"""


class Version(object):
    """
    Object representing the version of wasp.
    """
    def __init__(self, major, minor=-1, point=-1):
        """
        Initialize the object. Versions with the same major version number
        are downwards compatible. The API stays constant between
        point releases (i.e. no new features are added).
        :param major: (int) Major version number.
        :param minor: (int) Minor version number.
        :param point: (int) Point release number.
        """
        self.major = major
        self.minor = minor
        self.point = point

    def is_compatible(self, major, minor, point):
        """
        Check if another version is compatible with this version.
        :param major: (int) Major version number. Use -1 for "don't care"
        :param minor: (int) Minor version number. Use -1 for "don't care"
        :param point: (int) Point release number. Use -1 for "don't care"
        """
        if major == -1:
            return True
        if major != self.major:
            return False
        if minor == -1:
            return True
        if minor >= self.minor:
            return False
        if point == -1:
            return True
        if point >= self.point:
            return False


version = Version(0, 1, 0)
"""
Represents the version of this module.
"""


def require_version(*args):
    """
    Throws an AssertionError if the version specified in args is not
    compatible with the version of this module.
    :param args: a tuple of version numbers with (major, minor, point).
    Omitted numbers are treated as "don't care".
    """
    major = minor = point = -1
    if len(args) >= 1:
        major = args[0]
    if len(args) >= 2:
        minor = args[1]
    if len(args) >= 3:
        point = args[2]
    assert version.is_compatible(major, minor, point), 'Incompatible wasp version used.'


class FatalError(Exception):
    """
    Exception which is thrown if a fatal error occurs during the execution
    of the application.
    """
    pass


from .decorator_store import DecoratorStore
decorators = DecoratorStore()
"""
Acts as a central storage for storing functions registered using decorators.
decorators.<attribute-name> automatically returns a list, to which new items can be
appended. These lists are intended to be populated during the execution of decorators, i.e.
during the module load time. The lists can be read at a later stage of the application execution.
For example the @command decorator adds instances of the Command() class to decorators.commands.
After the modules have been loaded, the application reads decorators.commands and populates the command
list with it.
"""


from .platform import OSInfo
osinfo = OSInfo()
"""
Provides information about the operating system. For example, it can be determined, on which
platform the application is executed.
"""


from .logging import Logger
log = Logger(pretty=False)
"""
Logger object for the application. It provides the default logger for the application and
can be cloned (and modified) if a part of the application should log differently.
"""


from .util import Factory, Serializable, Namespace
factory = Factory()
"""
Factory object for registering Serializable types. Call :func:`wasp.util.Factory.register` for registering
a type and :func:`wasp.util.Factory.from_json` and `wasp.util.Factory.to_json` to (de-)serialize objects.
"""
factory.register(Namespace)


from .extension import ExtensionCollection, ExtensionMetadata
extensions = ExtensionCollection()
"""A collection of registered extensions"""

from .util import Proxy
ctx = Proxy()
# TODO: document


def recurse(*fpaths):
    """
    Tell wasp to recurse into the given paths. The paths
    are relative to top-directory. Recursion will not take place immediately
    but after the module loading has finished.
    :param fpaths: A tuple containing strings or lists thereof.
    """
    import os
    for f in fpaths:
        if isinstance(f, list):
            recurse(*f)
            continue
        assert isinstance(f, str), 'Arguments to recurse() must be strings or ' \
                                   'lists thereof. Found {0}'.format(type(f).__name__)
        if not os.path.isdir(f):
            f = os.path.dirname(f)
        _recurse_files.append(f)

_recurse_files = []
"""
A list of files which have been registered by :func:`recurse`
"""

from .context import Context
from .config import config, Config
from .option import options, handle_options, FlagOption, EnableOption, StringOption, IntOption
from .argument import Argument, value, arg, format_string, find_argumentkeys_in_string, ArgumentCollection
from .commands import command, Command, CommandFailedError
from .fs import Directory, File, copy, remove, paths, path, defer_install, find, find_exe, find_lib
from .fs import files, file, path, paths, directories, directory
from .task import Task, group, chain, task, TaskCollection, TaskGroup
from .shell import shell, ShellTask, quote
from .tools import tool
from .builtin import build, configure, install, alias, init
from .metadata import metadata, Metadata
from .node import Node, FileNode, SymbolicNode, nodes, node


ctx.__assign_object(Context())