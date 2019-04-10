from wasp import directory, Directory, file, factory, File
from wasp.fs import FileCollection


def prepare():
    curdir = directory(__file__)
    testdir = directory(curdir.join('test-dir'))
    testdir.remove(recursive=True)
    assert not testdir.exists
    testdir.mkdir()
    for f in ['a.txt', 'dira/dirb/b.txt', 'c.txt']:
        f = file(testdir.join(f))
        directory(f).mkdir()
        assert directory(f).exists
        with open(f.path, 'w') as fwrite:
            fwrite.write('asdf')
        assert f.exists


def test_directory():
    curdir = directory(__file__)
    testdir = directory(curdir.join('test-dir'))
    prepare()
    subdir = testdir.mkdir('subdir')
    assert isinstance(subdir, Directory)
    assert subdir.isdir
    assert subdir.exists
    assert isinstance(testdir.join('subdir'), Directory)
    home_dir = directory('~')
    assert subdir.relative(home_dir).absolute.path == subdir.absolute.path
    fs = [x.relative(testdir).path for x in testdir.glob('.*', dirs=False)]
    assert set(fs) == {'a.txt', 'dira/dirb/b.txt', 'c.txt'}
    fs = [x.relative(testdir).path for x in testdir.glob('.*', dirs=True, recursive=False)]
    assert set(fs) == {'a.txt', 'dira', 'c.txt', 'subdir'}
    fs = [x.relative(testdir).path for x in testdir.glob('.*', recursive=False, dirs=True, exclude='subdir')]
    assert set(fs) == {'a.txt', 'dira', 'c.txt'}
    testdir.join('dira').copy_to(subdir)
    assert set([x.relative(testdir).path for x in subdir.list()]) == {'subdir/dira'}
    subdir.remove()
    assert not subdir.exists
    subdir.mkdir()
    assert subdir.exists


def test_serialize():
    home_dir = directory('~')
    new_home_dir = factory.from_json(home_dir.to_json())
    assert home_dir.path == new_home_dir.path
    assert home_dir.relative_to == new_home_dir.relative_to


def test_file():
    curdir = directory(__file__)
    testdir = directory(curdir.join('test-dir'))
    prepare()
    f = testdir.join('a.txt')
    assert isinstance(f, File)
    assert not f.isdir
    assert f.extension == 'txt'
    f = f.append_extension('asdf')
    assert not f.exists
    assert f.extension == 'asdf'
    f = f.replace_extension('fdsa')
    assert f.extension == 'fdsa'


def test_file_collection():
    prepare()
    curdir = directory(__file__)
    testdir = directory(curdir.join('test-dir'))
    fs = testdir.glob('.*', dirs=False)
    col = FileCollection(fs)
    newcol = col.replace_extension('asdf')
    for f in newcol:
        assert f.extension == 'asdf'


if __name__ == '__main__':
    test_directory()
    test_serialize()
    test_file()
    test_file_collection()
