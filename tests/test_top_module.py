import wasp
import os
from wasp.main import load_directory, load_recursive
from tests import test_dir


def test_version():
    old_version = wasp.version

    wasp.version = wasp.Version(1, 0, 0)
    try:
        wasp.require_version(1, 1)
        compatible = True
    except AssertionError:
        compatible = False
    assert not compatible, 'Version should be incompatible'

    wasp.version = wasp.Version(1, 1, 0)
    try:
        wasp.require_version(1, 0, 3)
        compatible = True
    except AssertionError:
        compatible = False
    assert not compatible, 'Version should be compatible'

    wasp.version = wasp.Version(1, 3, 2)
    try:
        wasp.require_version(1, 2)
        compatible = True
    except AssertionError:
        compatible = False
    assert compatible, 'Version should be compatible'

    wasp.version = wasp.Version(1, 3, 2)
    try:
        wasp.require_version(1)
        compatible = True
    except AssertionError:
        compatible = False
    assert compatible, 'Version should be compatible'

    wasp.version = old_version


def test_recurse():
    os.chdir(os.path.join(test_dir, 'top_module_recurse'))
    loaded_files = load_directory('.')
    loaded_recursive = load_recursive()
    assert './build.py' in loaded_files
    assert './build.user.py' in loaded_files
    assert 'one/build.user.py' in loaded_recursive
    assert 'one/build.py' in loaded_recursive
    assert 'two/build.user.py' in loaded_recursive
    assert 'one/nested/build.user.py' in loaded_recursive
