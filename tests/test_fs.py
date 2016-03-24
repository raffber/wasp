from wasp import directory, Directory

curdir = directory(__file__)
testdir = curdir.join('test-dir')


def prepare():
    testdir.remove(recursive=True)
    testdir.ensure_exists()


def test_directory():
    prepare()
    subdir = testdir.mkdir('subdir')
    assert isinstance(subdir, Directory)
    assert isinstance(testdir.join('subdir'), Directory)
    fo


def test_serialize():
    pass


def test_file():
    prepare()


if __name__ == '__main__':
    test_directory()
