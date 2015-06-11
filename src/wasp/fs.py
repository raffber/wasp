"""
This module collects filesystem related functionality.

It introduces an abstraction for paths and files specifically
tailored to the usecases encountered in ``wasp``.
Furthermore, filesystem manipulating tasks are provides, such as
copy or remove functionality.

By default, all paths below :func:`top_dir` are relative to :func:`top_dir`
which is also the cwd of ``wasp``. All other paths are absolute. If a
:class:`File`, :class:`Path` or :class:`Directory` object is created, the
path is sanitized to this format using :func:`sanitize_path`.
"""
from itertools import chain
import os
import re
import shutil

from .node import FileNode
from .task import Task
from .util import Serializable, is_iterable, first
from . import factory, ctx
from .generator import Generator
from .argument import format_string, find_argumentkeys_in_string


def sanitize_path(fpath):
    """
    If the given path is a subdirectory of :func:`top_dir()`, the path is returned
    as relative path otherwise, the path is kept as an absolute paths
    :param fpath: path to a file
    :return: standardized path representation
    """
    assert isinstance(fpath, str), 'Path must be given as string.'
    fpath = os.path.realpath(fpath)
    top_dir = os.getcwd()
    is_subpath = os.path.commonprefix([fpath, top_dir]) == top_dir
    if is_subpath:
        fpath = os.path.relpath(fpath, start=top_dir)
    # else, leave it absolute
    return fpath


def top_dir():
    """
    Returns the top directory that wasp is currently processsing.
    :return: os.getcwd()
    """
    return os.getcwd()


class DirectoryNotEmptyError(Exception):
    """
    Raised if a directory is expected to be empty but it is not.
    """
    pass


class Path(Serializable):
    """
    Base class representing an object in the file system.

    :param path: Path refereing to the object.
    :param make_absolute: If True, the path is converted into an absolute path.
    :param relto: If a relative path is given in the ``path`` parameter the path is
        considered to be relative to relto.
    """

    def __init__(self, path, make_absolute=False, relto=None):
        if isinstance(path, Path) or isinstance(path, FileNode):
            path = path.path
        if make_absolute:
            path = os.path.realpath(path)
        elif relto is None:
            path = sanitize_path(path)
        if relto is not None and not os.path.isabs(relto):
            relto = os.path.abspath(relto)
        self._path = path
        self._relto = relto
        if not self.isabs and relto is None:
            self._relto = os.getcwd()
        self._absolute = make_absolute

    def copy(self):
        """
        Returns a copy of ``self``.
        """
        return Path(self.path, relto=self._relto, make_absolute=self._absolute)

    def relative(self, relto, skip_if_abs=False):
        """
        Returns a :class:`Path` object which is relative to ``relto``.

        :param relto: Defines the base path of the relative path to be constructed.
        :param skip_if_abs: If self is an absolute path, an absolute path is returned.
        """
        if isinstance(relto, Path):
            relto = relto.path
        if skip_if_abs and self.isabs:
            return Path(self, make_absolute=True)
        abspath = os.path.realpath(self._path)
        return Path(os.path.relpath(abspath, start=relto), relto=relto)

    def absolute(self):
        """
        Returns an absolute version of the path.
        """
        return Path(self._path, make_absolute=True)

    def relative_to(self):
        """
        Returns the path to which this path object is relative to.
        """
        return self._relto

    @property
    def isabs(self):
        """
        Returns true if the object is given as an absolute path.
        """
        return os.path.isabs(self._path)

    @property
    def path(self):
        """
        Returns the string the current path.
        """
        return self._path

    @property
    def exists(self):
        """
        Returns true if the path exists.
        """
        return os.path.exists(self._path)

    def __str__(self):
        """
        Equivalent to :func:`Path.path`.
        """
        return self._path

    @classmethod
    def from_json(cls, d):
        return cls(d['path'], make_absolute=d['absolute'], relto=d['relto'])

    def to_json(self):
        d = super().to_json()
        d.update({'path': self.path, 'absolute': self._absolute, 'relto': self._relto})
        return d

    def isdir(self):
        """
        Returns true if the path points to a directory.
        """
        return os.path.isdir(self.path)

    def remove(self, recursive=True):
        """
        Removes the path in the file system. If the path points
        to a directory and recursive is True, the whole directory tree
        below the path is removed. Otherwise, if the directory is not empty,
        a DirectoryNotEmptyError is raised.

        :param recursive: Defines whether the path should be removed in a recursive way, i.e.
            directories are removed including their content.
        """
        if not self.isdir():
            os.remove(self.path)
            return
        lst = os.listdir(self.path)
        if len(lst) != 0 and not recursive:
            raise DirectoryNotEmptyError('Directory not empty: `{0}`'.format(self.path))
        for path in lst:
            total = os.path.join(self.path, path)
            if not os.path.exists(total):
                continue  # we might have previously removed a symlink to this file
                # in this case, the removal might fail
            isdir = os.path.isdir(total)
            if isdir and recursive:
                Path(total).remove(recursive=True)
            elif isdir:
                try:
                    os.rmdir(total)
                except OSError:
                    pass
            else:
                Path(total).remove()

    def is_subpath(self, pth):
        # ensure that there is a `/` or whatever in the end
        pth = directory(pth)
        abspth = os.path.join(os.path.abspath(pth.path), '')
        absself = os.path.abspath(self.path)
        return absself.startswith(abspth)

    def to_builddir(self):
        """
        Returns a path object which is a subpath of the current build directory by
        prepending the build directory path to this path. If the path is already a subpath
        of the build directory, the copy of ``self`` is returned. For example,  if the build
        direcotory were ``build/``:

         * ``src/main.c`` becomes ``build/src/main.c``
         * ``/usr/lib/libglibc.so`` becomes ``build/usr/lib/libglibc.so``

        This function is useful when new files are created which somehow relate to a source
        file. E.g. when compiling ``src/main.c`` to an object file, the generated object file
        should be called something like ``build/src/main.c.o`` such that the user can easily
        find the generated files. This can be achieved with::

            file('src/main.c').to_builddir().append_extension('.o')
        """
        if self.is_subpath(ctx.builddir):
            return self.copy()
        return Path(ctx.builddir.join(self._path))

    def is_relative(self):
        """
        Returns True if this path is relative.
        """
        return not os.path.isabs(self._path)

    def basename(self):
        """
        Returns the basename of the path, i.e. its last component.
        For example ``src/main.c`` becomes ``main.c``.
        """
        return os.path.basename(self._path)


class Directory(Path):
    """
    Creates a directory object of the given path.
    If a path to a file is given, the directory name of the file is used.

    :param path: Path refereing to the object.
    :param make_absolute: If True, the path is converted into an absolute path.
    :param relto: If a relative path is given in the ``path`` parameter the path is
        considered to be relative to relto.
    """

    def __init__(self, path, make_absolute=False, relto=None):
        if isinstance(path, Path) or isinstance(path, FileNode):
            path = path.path
        if os.path.isfile(path):
            path = os.path.dirname(path)
        super().__init__(path, make_absolute=make_absolute, relto=relto)

    def copy(self):
        """
        Returns a copy of ``self``.
        """
        return Directory(self.path, relto=self._relto, make_absolute=self._absolute)

    def join(self, *args, append=''):
        """
        Joins the positional arguments as path and appends a string to them.

        :param append: String to append to path, e.g. a file extension.
        """
        new_args = []
        for arg in args:
            if isinstance(arg, File) or isinstance(arg, FileNode):
                new_args.append(arg.path)
            else:
                assert isinstance(arg, str), 'Expected either File, FileNode' \
                                             ' or str, but found `{0}`'.format(type(arg).__name__)
                new_args.append(arg)
        path = os.path.join(self.path, *new_args) + append
        if os.path.isdir(path):
            return Directory(path)
        if os.path.isfile(path):
            return File(path)
        return Path(path)

    def create(self):
        """
        Create the directory tree up to and including this directory.
        """
        os.makedirs(self._path, exist_ok=True)

    def glob(self, pattern, exclude=None, dirs=False, recursive=True):
        """
        Find files in this directory by using regex patterns. For example::

            directory('src/').glob('.*\.c$')

        finds all files ending in ``.c`` in the directory ``src`` but not in
        its subdirectories. If subdirectories should be searched as well,
        specify ``recursive=True``.

        :param pattern: Inclusion pattern. File names matching the pattern
            are included in the selection.
        :param exclude: Exclusion pattern. File names matching the pattern
            are excluded from the selection. Only files which match the
            inclusion pattern are tested.
        :param dirs: If True, directory names are considered as well.
        :param recursive: If True, the directory tree is searched recursively.
            Otherwise only this directory is searched.
        :return: List of path objects that match the above criteria.
        """
        ret = []
        include_re = re.compile(pattern)
        if exclude is not None:
            exclude_re = re.compile(exclude)
        else:
            exclude_re = None
        if recursive:
            abs_ = str(self.absolute())
            for dirpath, dirnames, filenames in os.walk(self._path):
                if dirs:
                    it = chain(dirnames, filenames)
                else:
                    it = filenames
                for f in it:
                    match_path = os.path.join(dirpath, f)
                    match_path = os.path.relpath(match_path, abs_)
                    m = include_re.match(match_path)
                    if m:
                        if exclude_re is not None and exclude_re.match(match_path):
                            continue
                        ret.append(os.path.join(self._path, match_path))
        else:
            for f in os.listdir(self._path):
                if not dirs and os.path.isdir(f):
                    continue
                m = include_re.match(f)
                if m:
                    if exclude_re is not None and exclude_re.match(f):
                        continue
                    newpath = os.path.join(self._path, f)
                    ret.append(newpath)
        new_ret = []
        for x in ret:
            if os.path.isdir(x):
                new_ret.append(Directory(x))
            else:
                new_ret.append(File(x))
        return new_ret

    def mkdir(self, name):
        """
        Create a child directory with ``name``.

        :param name: Name of the directory to be created.
        """
        fpath = os.path.join(self.path, name)
        d = Directory(fpath)
        d.ensure_exists()
        return d

    def ensure_exists(self):
        """
        Create the directory tree up to and including this directory.
        Equivalent to create().

        **TODO:** remove!
        """
        os.makedirs(self._path, exist_ok=True)

    def to_builddir(self):
        if self.is_subpath(ctx.builddir):
            return self.copy()
        return Directory(ctx.builddir.join(self._path))


factory.register(Directory)


class File(Path):
    """
    Creates a file object of the given path.

    :param path: Path refereing to the object.
    :param make_absolute: If True, the path is converted into an absolute path.
    :param relto: If a relative path is given in the ``path`` parameter the path is
        considered to be relative to relto.
    """

    def copy(self):
        """
        Returns a copy of ``self``.
        """
        return File(self.path, relto=self._relto, make_absolute=self._absolute)

    def directory(self):
        """
        :return: Instance of a Directory object representing the directory this script lives in.
        """
        return Directory(os.path.dirname(self._path))

    def replace_extension(self, new=None):
        """
        Returns a new File object, where the old extension is removed and replaced with the
        new extension.

        :param new: New extension. If None is given, the extension will be removed.
        :return: A new File object with the processed files.
        """
        if new is None:
            new = ''
        root, ext = os.path.splitext(self._path)
        return File(root + '.' + new, make_absolute=self._absolute)

    def append_extension(self, append):
        """
        Appends a new extension to the file name.

        :param append: String to be added to the file.
            This function ensures that a '.' is inserted
            between the file name and the extensions.
        """
        if append[0] == '.' or self._path[-1] == '.':
            return File(self._path + append)
        return File(self._path + '.' + append)

    def to_builddir(self):
        if self.is_subpath(ctx.builddir):
            return self.copy()
        return File(ctx.builddir.join(self._path))

    @property
    def extension(self):
        """
        Returns the extension of the file name. E.g.::

            File('src/main.c').extension

        return ``c``.
        """
        return os.path.splitext(self._path)[1]

factory.register(File)


class FileCollection(list):
    """
    Subclass of list which collects a objects of type :class:`File`.
    Allows the manipulation of may :class:`File` objects with one call.
    """

    def __init__(self, fs=None):
        super().__init__()
        if fs is None:
            return
        assert isinstance(fs, list) or isinstance(fs, File), \
            'A file collection can only be created from a File or a list thereof'
        if isinstance(fs, list):
            # a list of files, check if it containes only files
            # and extend self
            for f in fs:
                assert isinstance(f, File), 'A file collection can only be created from a File or a list thereof'
                self.append(File(f.path))  # clone the file object
        else:
            # a single file, just add it
            self.append(File(fs.path))

    def replace_extension(self, old=None, new=''):
        """
        Returns a new :class:``FileCollection` object with Files, where the old extension is removed and replaced with the
        new extension

        :param old: Extension to be processed. if None, all extensions are processd. Processed as regular expression.
        :param new: New extension. If an empty string is given, the extension will be removed.
        :return: A new FileCollection object with the processed files.
        """
        ret = FileCollection()
        if old is not None:
            old = re.compile(old)
        for f in self:
            m = old.match(f.extension)
            if old is not None and m is not None:
                ret.append(f.replace_extension(new))
                continue
            elif m is None:
                continue
            ret.append(f.replace_extension(new))
        return ret


def files(*args, ignore=False):
    """
    Returns a :class:``FileCollection` object based on the arguments. Accepts:

     * :class:`FileNode` A file node. Constructs a :class:`File` with the same path.
     * `str`: Uses the str as path.
     * :class:`File`: Appends the object to the collection
     * Iterable thereof.

    :param args: Tuple of one of the above types.
    :param ignore: Ignore invalid types. Can be used to squash all non-matching types.
    :return: A :class:`FileCollection` object.
    """
    ret = FileCollection()
    for f in args:
        if isinstance(f, FileNode):
            ret.append(File(f.path))
        elif isinstance(f, str):
            ret.append(File(f))
        elif isinstance(f, File):
            ret.append(f)
        elif is_iterable(f):
            ret.extend(files(*f))
        elif not ignore:
            raise ValueError('No compatible type given to `files()`.')
    return ret


def path(arg):
    """
    Returns a :class:`Path` object based on the argument. Accepts:

     * :class:`FileNode` A file node. Constructs a :class:`File` with the same path.
     * ``str``: Uses the ``str`` as path.
     * :class:`File` or :class:`Directory`: Appends the object to the collection.

    :param arg: Tuple of one of the above types.
    :return: An :class:`Path` object. If the path already exists and is a directory, a
        :class:`Directory` object is returned. Otherwise a :class:`File` object is
        returned.
    """
    if isinstance(arg, FileNode):
        return File(arg.path)
    elif isinstance(arg, str):
        if Path(arg).isdir():
            return Directory(arg)
        else:
            return File(arg)
    elif isinstance(arg, File):
        return arg
    elif isinstance(arg, Directory):
        return arg
    raise ValueError('No compatible type given to `path()`.')


def file(arg):
    """
    Returns a :class:`File` object base don the argument. Accepts:

        * :class:`FileNode`. Constructs a :class:`File` object with the same path.
        * ``str``: Uses the ``str`` as path.
        * :class:`Path`. Returns a :class:`File` object with the same path.

    :param arg: One of the above types.
    :return: A :class:`File` object based on the argument.
    """
    if isinstance(arg, str):
        return File(arg)
    elif isinstance(arg, FileNode):
        return File(arg.path)
    elif isinstance(arg, Path):
        return File(str(arg))
    raise ValueError('No compatible type given to `file()`'
                     ', type was `{0}`.'.format(arg.__class__.__name__))


def paths(*args, ignore=False):
    """
    Returns a list of :class:`Path` objects by calling the :meth:`path()` function.
    Accepts:

     * :class:`FileNode` A file node. Constructs a :class:`File` with the same path.
     * `str`: Uses the str as path.
     * :class:`File` or :class:`Directory`: Appends the object to the collection.
     * An iterable thereof.

    :param args: Tuple of one of the above types.
    :param ignore: Ignore invalid types. Can be used to squash all non-matching types.
    :return: A list of :class:`Path` objects.
    """
    ret = []
    for f in args:
        if is_iterable(f):
            ret.extend(paths(*f))
        else:
            try:
                p = path(f)
                ret.append(p)
            except ValueError as e:
                if not ignore:
                    raise e
    return ret


def directory(arg):
    """
    Returns a :class:`Directory` object base don the argument. Accepts:

        * :class:`FileNode`. Constructs a :class:`Directory` object with the path of the parent directory.
        * ``str``: Uses the ``str`` as path.
        * :class:`Directory`. Returns the same object.

    :param arg: One of the above types.
    :return: A :class:`Directory` object based on the argument.
    """
    if isinstance(arg, str):
        return Directory(arg)
    elif isinstance(arg, FileNode):
        return Directory(arg.path)
    elif isinstance(arg, Directory):
        return arg
    raise ValueError('No compatible type given to `directory()`'
                     ', type was `{0}`.'.format(arg.__class__.__name__))



def directories(*args, ignore=False):
    """
    Returns a list of :class:`Directory` objects.
    Accepts:

     * :class:`FileNode` A file node. Constructs a :class:`File` with the same path.
     * `str`: Uses the str as path of the directory.
     * :class:`File`: Uses the parent directory of the file.
     * :class:`Directory`: Appends the object to the collection.
     * An iterable thereof.

    :param args: Tuple of one of the above types.
    :param ignore: Ignore invalid types. Can be used to squash all non-matching types.
    :return: A list of :class:`Directory` objects.
    """
    ret = []
    for f in args:
        if isinstance(f, FileNode):
            ret.append(Directory(f.path))
        elif isinstance(f, str):
            ret.append(Directory(f))
        elif isinstance(f, File):
            ret.append(f.directory())
        elif isinstance(f, Directory):
            ret.append(f)
        elif isinstance(f, Path):
            ret.append(Directory(f.path))
        elif is_iterable(f):
            ret.extend(directories(*f))
        elif not ignore:
            raise ValueError('No compatible type given to `directories()`'
                             ', type was `{0}`.'.format(f.__class__.__name__))
    return ret


class FindTask(Task):
    """
    Task to find files in the file system. It looks for different
    combinations of file names and directories and once it
    has found a matching path, it is saved into all targets of type :class:`wasp.node.SymbolicNode`.
    By default, the following keys are written to the target nodes:

        * argprefix + 'file`: The file path
        * argprefix + 'dir': The directory path containing the file

    :param *names: Tuple of str of acceptable file names
    :param dirs: List of directories to search in. Accepts the same input as :func:`directories`
    :param argprefix: str prefix to be added to the keys which are saved in the target nodes.
    :param required: True if the task should fail if the file path is not found.
    """
    def __init__(self, *names, dirs=None, argprefix=None, required=True):
        super().__init__(always=True)
        self._dirs = directories(dirs)
        self._names = list(names)
        if argprefix is None:
            argprefix = list(self._names)
        elif isinstance(argprefix, str):
            argprefix = [argprefix]
        assert isinstance(argprefix, list)
        self._argprefix = argprefix
        self._required = required

    def _run(self):
        found = False
        result_file = ''
        result_dir = ''
        for d in self._dirs:
            if found:
                break
            for name in self._names:
                f = File(d.join(name))
                if f.exists:
                    result_file = f.path
                    result_dir = str(d)
                    found = True
                    break
        if self._required and not found:
            self._success = False
            self._print_fail()
        else:
            self._print_success(result_file, result_dir)
            self._success = True
        # transmit all arguments to result
        self.result = self.arguments
        # augment the arguments
        for ap in self._argprefix:
            self.result[ap] = result_file
        self._store_result(result_file, result_dir)

    def _store_result(self, file, dir):
        pass

    def _print_fail(self):
        self.log.log_fail('Cannot find required file! Looking for: [{0}]'.format(', '.join(self._names)))

    def _print_success(self, file, dir):
        self.log.log_success('Found file `{0}` in `{1}`'.format(file, dir))


def find(*names, dirs=None, argprefix=None, required=True):
    """
    See :class:`FindTask`. Accepts the same parameters.
    """
    FindTask(*names, dirs=dirs, argprefix=argprefix, required=required)


class FindExecutable(FindTask):
    """
    Looks for executables. If ``dirs`` is not specified, the all paths in the ``PATH`` variable
    are searched. This tasks writes the following arguments to the target nodes:
        * argprefix + 'file`: The file path
        * argprefix + 'exe': The file path
        * argprefix + 'dir': The directory path containing the file
    """
    def __init__(self, *args, dirs=None, **kw):
        if dirs is None:
            dirs = os.getenv('PATH').split(':')
        super().__init__(*args, dirs=dirs, **kw)

    def _store_result(self, file, dir):
        pass


def find_exe(*names, dirs=None, argprefix=None, required=True):
    """
    See :class:`FindExecutable`. Accepts the same parameters.
    """
    return FindExecutable(*names, dirs=dirs, argprefix=argprefix, required=required)


class FindLibrary(FindTask):
    """
    Looks for executables. If ``dirs`` is not specified, the all paths in the ``LD_LIBRARY_PATH`` variable
    are searched. This tasks writes the following arguments to the target nodes:
        * argprefix + 'lib`: The file path
        * argprefix + 'exe': The file path
        * argprefix + 'dir': The directory path containing the file
    """
    def __init__(self, *args, dirs=None, **kw):
        if dirs is None:
            dirs = os.getenv('LD_LIBRARY_PATH').split(':')
        super().__init__(*args, dirs=dirs, **kw)

    def _store_result(self, file, dir):
        pass


def find_lib(*names, dirs=None, argprefix=None, required=True):
    """
    See :class:`FindLibrary`. Accepts the same parameters.
    """
    return FindLibrary(*names, dirs=dirs, argprefix=argprefix, required=required)


class RemoveTask(Task):
    """
    Removes a list of paths from the file system.
    :param fs: List of files to be removed. Accepts the same inputs as :func:`paths`.
    :param recursive: Determines whether directories should be removed recursively or not.
        If recursive is False and a directory is not empty, the task fails.
    """

    def __init__(self, fs, recursive=False):
        self._recursive = recursive
        self._files = paths(fs, ignore=True)
        super().__init__(targets=fs, always=True)

    def _run(self):
        try:
            for f in self._files:
                f.remove(recursive=self._recursive)
            msg = 'Removed: [{0}]'.format(', '.join(f.path for f in self._files))
            self.log.info(self.log.format_success(msg))
            self.success = True
        except DirectoryNotEmptyError:
            msg = 'Failed to remove `{0}`: Directory is ' \
                  'not empty! (and recursive = {1})'.format(str(f), self._recursive)
            self.log.fatal(self.log.format_fail(msg))
            self.success = False
        except OSError as e:
            msg = 'Failed to remove `{0}`: {1}'.format(str(f), str(e))
            self.log.fatal(self.log.format_fail(msg))
            self.success = False


def remove(*args, recursive=False):
    """
    See :class:`RemoveTask`. Accepts the same parameters.
    """
    return RemoveTask(args, recursive=recursive)


BINARY_PERMISSIONS = 0o755
DEFAULT_PERMSSIONS = 0o644


class CopyTask(Task):
    """
    Task to copy files.

    :param fs: List of files to be copied. Accepts the same input as :func:`paths`.
    :param destination: Destination path. If it ends with a '/' (or '\\') the destination
        is considered a directory and a new file is created in the directory.
    :param permsissions: UNIX style representation of permissions (typically given in octal).
    :param recursive: Determines whether directories are to be copied recursively.
    """
    # TODO: port to windows....

    def __init__(self, fs, destination, permissions=None, recursive=False):
        self._recursive = recursive
        self._permissions = permissions
        if isinstance(destination, str):
            if destination.endswith('/') or destination.endswith('\\'):
                destination = Directory(destination)
            else:
                destination = File(destination)
        assert isinstance(destination, Path)
        self._destination = destination
        self._files = paths(fs, ignore=True)
        super().__init__(targets=fs, always=True)

    def _run(self):
        self.success = True
        for f in self._files:
            destpath = self._destination.path
            formatted = format_string(destpath, self.arguments)
            try:
                if self._recursive:
                    shutil.copytree(str(f), formatted)
                else:
                    shutil.copy2(str(f), formatted)
                if self._permissions is not None:
                    os.chmod(formatted, self._permissions)
                msg = 'Copy {0} to {1}'.format(str(f), formatted)
                self.log.info(self.log.format_success(msg))
            except OSError as e:
                msg = 'Failed to copy `{0}` to `{1}`: {2}'.format(str(f), formatted, str(e))
                self.log.fatal(self.log.format_fail(msg))
                self.success = False
                break


def copy(source, destination, permissions=None, recursive=False):
    """
    See :class:`CopyTask`. Accepts the same parameters.
    """
    return CopyTask(source, destination, permissions=permissions, recursive=recursive)


class FileInstallGenerator(Generator):

    def __init__(self, fpaths, destination='{PREFIX}/share/{PROJECTID}', permissions=DEFAULT_PERMSSIONS):
        self._destination = Directory(destination)
        self._permissions = permissions
        self._files = files(fpaths)

    @property
    def key(self):
        return '-'.join([str(x) for x in self._files])

    @property
    def destination(self):
        return self._destination

    @property
    def permissions(self):
        return self._permissions

    def run(self):
        ret = []
        require = find_argumentkeys_in_string(str(self.destination))
        for f in self._files:
            cp = copy(f, self._destination.join(f.basename())).require(require)
            ret.append(cp)
        return ret

    @classmethod
    def from_json(cls, d):
        return cls(factory.from_json(d['files'])
                   , permissions=d['permissions']
                   , destination=factory.from_json(d['destination']))

    def to_json(self):
        d = super().to_json()
        d['files'] = factory.to_json(self._files)
        d['permissions'] = self.permissions
        d['destination'] = self._destination.to_json()
        return d


factory.register(FileInstallGenerator)


def defer_install(file, destination='{PREFIX}/share/{PROJECTID}', permissions=DEFAULT_PERMSSIONS, command='install'):
    ctx.generators(command).add(FileInstallGenerator(file, destination=destination, permissions=permissions))
