from .util import load_module_by_path


def run_file(fpath):
    module = load_module_by_path(fpath)
