from wasp import ArgumentCollection, Argument, arg, value, ctx, Metadata
from wasp import format_string, find_argumentkeys_in_string
from . import setup_context, destroy_context


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
    meta = Metadata()
    meta.foo = 'bar'
    setup_context(meta=meta)
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
    destroy_context()


def test_argument_retrieve_all():
    pass



def test_argument_collection_simple():
    pass


def test_argument_collection_hierarchical():
    pass


def test_format_string():
    pass

def test_argument_shortcuts():
    pass
