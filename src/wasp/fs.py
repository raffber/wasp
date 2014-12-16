import os
import re
import shutil

from .node import FileNode
from .task import Task
from .util import Serializable, is_iterable
from . import factory, ctx
from .generator import Generator
from .argument import format_string, find_argumentkeys_in_string
from glob import glob

MODULE_DIR = os.path.realpath(os.path.dirname(__file__))
# TODO: this might cause problems if the extraction path of wasp is changed.
# but how to fix it? Is a fix relevant?!
TOP_DIR = os.path.realpath(os.path.join(MODULE_DIR, '../..'))


def sanitize_path(fpath):
    """
    If the given path is a subdirectory of TOP_DIR, the path is saved as relative path
    otherwise, the path is kept as an absolute paths
    :param fpath: path to a file
    :return: standardized path representation
    """
    assert isinstance(fpath, str), 'Path must be given as string.'
    fpath = os.path.realpath(fpath)
    is_subpath = os.path.commonprefix([fpath, TOP_DIR]) == TOP_DIR
    if is_subpath:
        fpath = os.path.relpath(fpath, start=TOP_DIR)
    # else, leave it absolute
    return fpath


class DirectoryNotEmptyError(Exception):
    pass


class Path(Serializable):

    def __init__(self, path, make_absolute=False):
        if isinstance(path, Path) or isinstance(path, FileNode):
            path = path.path
        if make_absolute:
            path = os.path.realpath(path)
        else:
            path = sanitize_path(path)
        self._path = path
        self._absolute = make_absolute


    @property
    def path(self):
        return self._path

    @property
    def exists(self):
        """Checks if the path exits"""
        return os.path.exists(self._path)

    def __str__(self):
        return self._path

    @classmethod
    def from_json(cls, d):
        return cls(d['path'], make_absolute=d['absolute'])

    def to_json(self):
        d = super().to_json()
        d.update({'path': self.path, 'absolute': self._absolute})
        return d

    def isdir(self):
        return os.path.isdir(self.path)

    def remove(self, recursive=True):
        if not self.isdir():
            os.remove(self.path)
            return
        lst = os.listdir(self.path)
        if len(lst) != 0 and not recursive:
            raise DirectoryNotEmptyError('Directory not empty: `{0}`'.format(self.path))
        for path in lst:
            total = os.path.join(self.path, path)
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


def paths(*args):
    ret = []
    for item in args:
        if isinstance(item, Path):
            ret.append(item)
        elif isinstance(item, str):
            ret.append(Path(item))
        elif isinstance(item, FileNode):
            ret.append(Path(item.path))
        elif is_iterable(item):
            ret.extend(paths(*item))
    return ret


class Directory(Path):
    # TODO: implement serializable

    def __init__(self, path, make_absolute=False):
        """
        Creates a directory object of the given path.
        If a path to a file is given, the directory name of the file is used.
        :param path: Path to a directory or path to a file.
        :param make_absolute: Defines whether the directory should be handleded as an absolute directory or a relative one.
        """
        if isinstance(path, Path) or isinstance(path, FileNode):
            path = path.path
        if os.path.isfile(path):
            path = os.path.dirname(path)
        super().__init__(path, make_absolute=make_absolute)

    def join(self, *args, append=''):
        """Joins the positional arguments as path and appends a string to them"""
        new_args = []
        for arg in args:
            if isinstance(arg, File) or isinstance(arg, FileNode):
                new_args.append(arg.path)
            else:
                assert isinstance(arg, str), 'Expected either File, FileNode' \
                                             ' or str, but found `{0}`'.format(type(arg).__name__)
                new_args.append(arg)
        return os.path.join(self.path, *new_args) + append

    def glob(self, pattern, exclude=None, dirs=True):
        """
        Finds all path names in the directory according to unix-shell rules. The exculde pattern
        is given in regular expressions. This method uses glob.glob() internally.
        :param pattern: Unix-shell like pattern to match.
        :param dirs: If True, directories are matched as well, otherwise, they are excluded
        :param exclude: Regular expression pattern for exculding files.
        """
        ret = []
        exculde_pattern = re.compile(exclude)
        globs = glob(os.path.join(self.path, pattern))
        for x in globs:
            m = exculde_pattern.match(x)
            if m:
                continue
            if os.path.isdir(x) and not dirs:
                continue
            ret.append(x)
        return ret

    def ensure_exists(self):
        try:
            os.makedirs(self._path)
        except FileExistsError:
            pass


factory.register(Directory)


class File(Path):

    def directory(self):
        """
        :return: Instance of a Directory object representing the directory this script lives in.
        """
        return Directory(os.path.dirname(self._path))

    def replace_extension(self, new):
        """
        Returns a new File object, where the old extension is removed and replaced with the
        new extension
        :param new: New extension. If an empty string is given, the extension will be removed.
        :return: A new File object with the processed files.
        """
        root, ext = os.path.splitext(self._path)
        return File(root + new, make_absolute=self._absolute)

    def append_extension(self, append):
        if append[0] == '.' or self._path[-1] == '.':
            return File(self._path + append)
        return File(self._path + '.' + append)

    def to_builddir(self):
        return File(ctx.builddir.join(self._path))

    def is_relative(self):
        return not os.path.isabs(self._path)

    def basename(self):
        return os.path.basename(self._path)

    @property
    def extension(self):
        return os.path.splitext(self._path)[1]

factory.register(File)


class FileCollection(list):

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
        Returns a new FileCollection object with Files, where the old extension is removed and replaced with the
        new extension
        :param old: Extension to be processed. if None, all extensions are processd. Processed as regular expression.
        :param new: New extension. If an empty string is given, the extension will be removed.
        :return: A new FileCollection object with the processed files.
        """
        ret = FileCollection()
        if old is not None:
            old = re.compile(old)
        for f in self:
            if old is not None and old.match(f.extension):
                ret.append(f.replace_extension(new))
                continue
            ret.append(f.replace_extension(new))
        return ret


def files(*args, ignore=False):
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
            raise ValueError('No compatible type given to `files()`. Expected FileNode, str or File.')
    return ret


class RemoveFileTask(Task):

    def __init__(self, fs, recursive=False):
        self._recursive = recursive
        self._files = files(fs, ignore=True)
        super().__init__(targets=fs, always=True)

    def _run(self):
        for f in self._files:
            f.remove()
        self.success = True


factory.register(RemoveFileTask)


def remove(*args, recursive=False):
    return RemoveFileTask(args, recursive=recursive)


BINARY_PERMISSIONS = 0o755
DEFAULT_PERMSSIONS = 0o644


class CopyFileTask(Task):

    def __init__(self, fs, destination, permissions=DEFAULT_PERMSSIONS, recursive=False):
        self._recursive = recursive
        self._permissions = permissions
        self._destination = Directory(destination)
        self._files = files(fs, ignore=True)
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
                os.chmod(formatted, self._permissions)
            except OSError as e:
                self.log.fatal('Failed to copy `{0}` to `{1}`: {2}'.format(str(f), formatted, str(e)))
                self.success = False
                break


def copy(source, destination, permissions=None, recursive=False):
    return CopyFileTask(source, destination, permissions=permissions, recursive=recursive)


factory.register(CopyFileTask)


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