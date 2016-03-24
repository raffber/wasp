from wasp import directory, Directory, file, factory

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
        f = testdir.join(file(f))
        directory(f).ensure_exists()
        assert directory(f).exists
        with open(f.path, 'w') as fwrite:
            fwrite.write('asdf')
        assert file(f).exists
    fs = [x for x in testdir.glob('.*', dirs=False)]
    assert fs == ['a.txt', 'dira/dirb/b.txt', 'c.txt']


def test_serialize():
    home_dir = directory('~')
    new_home_dir = factory.from_json(home_dir.to_json())
    assert home_dir.path == new_home_dir
    assert home_dir.relative_to == new_home_dir.relative_to


def test_file():
    prepare()


if __name__ == '__main__':
    test_directory()
    test_serialize()
    test_file()
