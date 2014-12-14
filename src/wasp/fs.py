import os
import re
from .node import FileNode
from .task import Task
from .util import Serializable
from . import factory, ctx
from .generator import Generator

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


class Directory(Serializable):
    # TODO: implement serializable

    def __init__(self, path, make_absolute=False):
        """
        Creates a directory object of the given path.
        If a path to a file is given, the directory name of the file is used.
        :param path: Path to a directory or path to a file.
        :param make_absolute: Defines whether the directory should be handleded as an absolute directory or a relative one.
        """
        if make_absolute:
            path = os.path.realpath(path)
        else:
            path = sanitize_path(path)
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self._path = path

    def join(self, *args, append=''):
        """Joins the positional arguments as path and appends a string to them"""
        return os.path.join(self.path, *args) + append

    @property
    def valid(self):
        """Checks if the directory exits"""
        return os.path.isdir(self._path)

    @property
    def path(self):
        return self._path

    def glob(self, pattern, recusive=False, exclude=None):
        raise NotImplementedError

    def ensure_exists(self):
        try:
            os.makedirs(self._path)
        except FileExistsError:
            pass

    def __str__(self):
        return self._path


factory.register(Directory)


class File(Serializable):
    # TODO: implement serializable

    def __init__(self, path, make_absolute=False):
        """
        Initializes a file object with the given path.
        :param path: Path to the file. The file may or may not exist.
        :param make_absolute: Make the path absolute in all cases.
        """
        assert isinstance(path, str), 'Path to file must be given as a string'
        if make_absolute:
            self._path = os.path.realpath(path)
        else:
            self._path = sanitize_path(path)
        self._absolute = make_absolute

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

    @property
    def extension(self):
        return os.path.splitext(self._path)[1]

    @property
    def path(self):
        return self._path

    def __str__(self):
        return self._path


factory.register(File)


class FileCollection(list):

    def __init__(self, fs):
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


def file(arg):
    if isinstance(arg, FileNode):
        return File(arg.path)
    elif isinstance(arg, str):
        return File(arg)


def files(*args):
    if len(args) == 1:
        if isinstance(args, list):
            return files(*args)
    ret = FileCollection()
    for f in args:
        if isinstance(f, FileNode):
            ret.append(File(f.path))
        elif isinstance(f, str):
            ret.append(File(f))
    return ret


class RemoveTask(Task, Serializable):

    def __init__(self, fs, recursive=False):
        self._recursive = recursive
        super().__init__(targets=fs, always=True)

    def _make_id(self):
        return 'rm ' + ' '.join(files)

    def _run(self):
        raise NotImplementedError
        # # TODO: implement recursive
        # for f in self.files:
        #     os.remove(f)

    def to_json(self):
        raise NotImplementedError

    @classmethod
    def from_json(cls, d):
        raise NotImplementedError


factory.register(RemoveTask)


def remove(*args):
    raise NotImplementedError


def copy(source, destination, flags=None):
    raise NotImplementedError


BINARY_PERMISSIONS = 755
DEFAULT_PERMSSIONS = 644


class FileInstallGenerator(Generator):

    def __init__(self, fpaths, destination='{PREFIX}/share/{PROJECTID}', permissions=BINARY_PERMISSIONS):
        self._destination = destination
        self._files = files(fpaths)

    @property
    def key(self):
        return '-'.join(str(self._files))

    @property
    def destination(self):
        return self._destination

    def run(self):
        ret = []
        destdir = Directory(self.destination)
        for f in self._files:
            cp = copy(f, destdir.join(f)).require_all()
            ret.append(cp)
        return ret

    @classmethod
    def from_json(cls, d):
        raise NotImplementedError

    def to_json(self):
        raise NotImplementedError


factory.register(FileInstallGenerator)


def defer_install(file, destination='{PREFIX}/share/{PROJECTID}', permissions=DEFAULT_PERMSSIONS, command='install'):
    ctx.generators(command).add(FileInstallGenerator(file, destination=destination, permissions=permissions))