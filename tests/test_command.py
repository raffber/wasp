from tests import setup_context
from wasp import ctx
from wasp.commands import Command


def test_commands():
    setup_context()
    com = Command('build', _test_commandfun, description='Build a command.',
            depends='configure', produce=':build', option_alias='test', skip_as_depenency=True)
    assert com.name == 'build'
    assert com.depends[0] == 'configure'
    assert com.run() == 'result-of-testfun'
    command_cache = ctx.cache.prefix('commands')
    command_cache['build'] = {}
    command_cache['build']['success'] = True
    assert com.run(True) is None


def _test_commandfun():
    return 'result-of-testfun'


