from tests import setup_context
from wasp import ctx


def test_g():
    setup_context()
    failed = False
    try:
        foobar = ctx.g.test
    except AttributeError:
        failed = True
    assert failed
    ctx.g.test = {'foo': 'bar'}
    assert ctx.g.test['foo'] == 'bar'
