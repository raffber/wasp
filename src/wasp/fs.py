import os
import re
from .node import FileNode
from .task import Task, register_task
from .util import Serializable

MODULE_DIR = os.path.realpath(os.path.dirname(__file__))
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


class Directory(object):
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

    def glob(self, pattern, recusive=False):
        # TODO: implement
        raise NotImplementedError

    def ensure_exists(self):
        try:
            os.makedirs(self._path)
        except FileExistsError:
            pass


class File(object):

    def __init__(self, path, make_absolute=False):
        """
        Initializes a file object with the given path.
        :param path: Path to the file. The file may or may not exist.
        :param make_absolute: Make the path absolute in all cases.
        """
        if make_absolute:
            self._path = os.path.realpath(path)
        else:
            self._path = sanitize_path(path)
        self._absolute = make_absolute

    def replace_extension(self, new):
        """
        Returns a new File object, where the old extension is removed and replaced with the
        new extension
        :param new: New extension. If an empty string is given, the extension will be removed.
        :return: A new File object with the processed files.
        """
        root, ext = os.path.splitext(self._path)
        return File(root + new, make_absolute=self._absolute)

    @property
    def extension(self):
        return os.path.splitext(self._path)[1]


class FileCollection(list):

    def __init__(self, files):
        assert isinstance(files, list) or isinstance(files, File), \
            'A file collection can only be created from a File or a list thereof'
        if isinstance(files, list):
            # a list of files, check if it containes only files
            # and extend self
            for f in files:
                assert isinstance(f, File), 'A file collection can only be created from a File or a list thereof'
                self.append(File(f.path))  # clone the file object
        else:
            # a single file, just add it
            self.append(File(files.path))

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

    def __init__(self, files, recursive=False):
        self._recursive = recursive
        super().__init__(targets=files, always=True)

    def _make_id(self):
        return 'rm ' + ' '.join(files)

    def _run(self):
        # TODO: implement recursive
        for f in files:
            os.remove(f)


def remove(*args):
    raise NotImplementedError
