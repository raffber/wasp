from tests import setup_context
from wasp import ArgumentCollection, Argument, arg, value, ctx, Metadata, FlagOption, Context, StringOption
from wasp import format_string, find_argumentkeys_in_string
from wasp.option import OptionsCollection


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
    col.add(StringOption('foo', 'Enables foo for testing.', keys='somethingelse'))
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
    arg = Argument('foo').retrieve('bar')
    col = ArgumentCollection()
    assert col.isempty()
    col.add(arg)
    assert not col.isempty()
    assert col['foo'] == arg
    col = ArgumentCollection.from_dict({'test': 'ing'})
    assert col['test'].value == 'ing'
    col1 = ArgumentCollection()
    col2 = ArgumentCollection()
    col1['foo'] = 'bar'
    col2['foo'] = 'test'
    assert col1.get('foo').value == 'bar'
    assert col2.get('asdf') is None
    col1.overwrite_merge(col2)
    assert col1['foo'].value == 'test'
    assert col.value('invalid') is None
    assert col.value('test') == 'ing'


def test_format_string():
    col = ArgumentCollection()
    col.add(arg('foo', value='bar'))
    ret = format_string('Test: {foo} test', col)
    assert ret == 'Test: bar test'
    ret = find_argumentkeys_in_string('Test: {foo} and {bar} so on')
    assert 'foo' in ret and 'bar' in ret

