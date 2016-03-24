from wasp import directory, Directory, file

curdir = directory(__file__)
testdir = curdir.join('test-dir')


def prepare():
    testdir.remove(recursive=True)
    testdir.ensure_exists()


def test_directory():
    prepare()
    subdir = testdir.mkdir('subdir')
    assert isinstance(subdir, Directory)
    assert subdir.isdir
    assert subdir.exists
    assert isinstance(testdir.join('subdir'), Directory)
    home_dir = directory('~')
    assert subdir.relative(home_dir).absolute == subdir.absolute
    for f in ['a.txt', 'dira/dirb/b.txt', 'c.txt']:
        f = file(f)
        directory(f).ensure_exists()
        with open(f.path, 'w') as fwrite:
            fwrite.write('asdf')
    assert


def test_serialize():
    pass


def test_file():
    prepare()


if __name__ == '__main__':
    test_directory()
