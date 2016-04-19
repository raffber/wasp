from wasp import Metadata


def test_metadata():
    meta = Metadata()
    assert meta.projectname == 'myproject'
    assert meta.projectid == 'myproject'
    meta.projectname = 'foo'
    assert meta.projectname == 'foo'
    assert meta.projectid == 'foo'
    meta.projectid = 'bar'
    assert meta.projectid == 'bar'
    meta.projectname = 'foobar'
    assert meta.projectid == 'bar'
    meta.foobar = 'foobar'
    assert meta.foobar == 'foobar'
    assert meta.as_dict() == {'projectname': 'foobar', 'foobar': 'foobar', 'projectid': 'bar'}
