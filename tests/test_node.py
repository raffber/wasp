from wasp.fs import directory
from wasp import FileNode, SymbolicNode, ArgumentCollection
from tests import setup_context


def test_file_node():
    setup_context()
    curdir = directory(__file__)
    testdir = curdir.join('test-dir')
    testdir.remove()
    testdir.ensure_exists()
    testfile = testdir.join('test-file.txt').path
    node = FileNode(testfile)
    node.signature().refresh()
    assert node.signature().value is None
    assert node.signature().valid
    with open(testfile, 'w') as f:
        f.write('asdf')
    node.signature().refresh()
    assert node.signature().valid
    v = node.signature().value
    assert v is not None
    with open(testfile, 'w') as f:
        f.write('blabla')
    node.signature().refresh()
    assert node.signature().valid
    newv = node.signature().value
    assert newv != v
    assert newv is not None
    with open(testfile, 'w') as f:
        f.write('asdf')
    node.signature().refresh()
    assert node.signature().value == v


def test_symbolic_node():
    setup_context()
    node = SymbolicNode('asdf')
    data = node.read()
    node.signature().refresh()
    assert node.signature().valid
    assert node.signature().value is None
    assert isinstance(data, ArgumentCollection)
    data.update(x=3)
    assert data['x'].value == 3
    node.write(data)
    node.signature().refresh()
    assert node.signature().valid
    v = node.signature().value
    assert v is not None
    node2 = SymbolicNode('asdf')
    assert node2.read()['x'].value == 3
    assert node2.signature().value == v


if __name__ == '__main__':
    test_file_node()
    test_symbolic_node()

