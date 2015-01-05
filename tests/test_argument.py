from . import setup_context
from wasp import ArgumentCollection, Argument, arg, value, ctx, Metadata, FlagOption, Context
from wasp import format_string, find_argumentkeys_in_string
from wasp.options import OptionsCollection


def test_argument():
    arg = Argument('foo', value=[1, 2, 3])
    assert arg.type == list
    try:
        arg.value = 'asdf'
        failed = False
    except TypeError:
        failed = True
    assert failed
    arg = Argument('foo')
    arg.value = {1: 3, 4: 5}
    assert arg.type == dict
    arg.value = {3: 4, 5: 6}
    arg = Argument('foo', type=list)
    try:
        arg.value = 'asdf'
        failed = False
    except TypeError:
        failed = True
    assert failed
    arg.value = [1, 2, 3, 4]


def test_argument_retrieve():
    setup_context()
    meta = Metadata()
    meta.foo = 'bar'
    ctx.__assign_object(Context())
    ctx.meta = meta
    # test retrieval from ctx.env
    ctx.env['FOO'] = 'bar'
    arg = Argument('foo').retrieve(ctx.env)
    assert arg.value == 'bar'
    # test if argument is not present
    del ctx.env['FOO']
    arg = Argument('foo').retrieve(ctx.env)
    arg.retrieve(ctx.env)
    assert arg.value is None
    assert arg.is_empty
    # test retrieval from meta
    arg = Argument('foo').retrieve(ctx.meta)
    assert arg.value == 'bar'

    col = OptionsCollection()
    col.add(FlagOption('foo', 'Enables foo for testing.', keys='somethingelse'))
    col.retrieve_from_dict({'foo': 'bar'})
    arg = Argument('foo').retrieve(col)
    assert arg.value == 'bar'

    arg = Argument('foo').retrieve({'foo': 'bar'})
    assert arg.value == 'bar'

    col = ArgumentCollection.from_dict({'foo': 'bar'})
    arg = Argument('foo').retrieve(col)
    assert arg.value == 'bar'

    arg = Argument('foo').retrieve('bar')
    assert arg.value == 'bar'


def test_argument_collection():
    col = ArgumentCollection()
    subcol = col('group')
    subcol.add(Argument('foo', value='child-value'))
    assert col.value('foo') is None
    assert 'foo' not in col
    assert subcol.value('foo') == 'child-value'
    col.add(Argument('foo', value='parent-value'))
    assert col['foo'].value == 'parent-value'
    assert col('group').value('foo') == 'child-value'
    for arg in col.values():
        assert arg.value == 'parent-value'
        assert arg.key == 'foo'
    for arg in col('group').values():
        assert arg.value == 'child-value'
        assert arg.key == 'foo'
    d = col.to_json()
    col = ArgumentCollection.from_json(d)
    assert col('group').value('foo') == 'child-value'
    assert col.value('foo') == 'parent-value'
    col = col.copy()
    assert col('group').value('foo') == 'child-value'
    assert col.value('foo') == 'parent-value'


def test_format_string():
    col = ArgumentCollection()
    col.add(arg('foo', value='bar'))
    ret = format_string('Test: {foo} test', col)
    assert ret == 'Test: bar test'
    ret = find_argumentkeys_in_string('Test: {foo} and {bar} so on')
    assert 'foo' in ret and 'bar' in ret

