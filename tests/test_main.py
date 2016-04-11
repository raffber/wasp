from tests import setup_context
from wasp import decorators, Command, FlagOption, EnableOption, Argument, ArgumentCollection
from wasp.main import OptionHandler
from wasp import StringOption, IntOption
from wasp.option import ArgumentOption
from wasp import ctx



# TODO:
# test alias
# test different keys
# test prefixes
# test how option strings are converted to argument strings


def options_fun(opt):
    opt.group('build').add(StringOption('hello', 'Specifies the hello description'))
    opt.group('build').add(IntOption('foo', 'Allows specifying a number foo'))
    opt.add(ArgumentOption('argopt', 'Specifies an argument'))
    opt.add(FlagOption('foobar', 'Defines whether to foobar or not'))
    opt.add(EnableOption('something', 'Specifies whether something should be enabled'))


def build_fun():
    pass


def test_options():
    setup_context()
    decorators._other.clear()
    decorators.options = options_fun
    assert decorators.options == [options_fun]
    decorators.commands = Command('build', build_fun)
    handler = OptionHandler()
    handler.parse(['--foobar', '--enable-something',
                   '--argopt', 'foo=bar', 'build', '--foo', '1234',
                   '--hello', 'world'])
    assert handler.commands == ['build']
    assert ctx.options['foobar'].value
    assert ctx.options['something'].value
    arg = ctx.options['argopt'].value
    assert isinstance(arg, ArgumentCollection)
    arg = arg['foo']
    assert isinstance(arg, Argument)
    assert arg.name == 'foo'
    assert arg.value == 'bar'
    # TODO: more testing


if __name__ == '__main__':
    test_options()
