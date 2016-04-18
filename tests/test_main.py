from tests import setup_context
from wasp import decorators, Command, FlagOption, EnableOption, Argument, ArgumentCollection
from wasp.main import OptionHandler, retrieve_command_tasks, NoSuchCommandError
from wasp import StringOption, IntOption
from wasp.option import ArgumentOption
from wasp import ctx, command, Task



# TODO:
# test alias
# test how option strings are converted to argument strings


def options_fun(opt):
    opt.group('build').add(StringOption('hello', 'Specifies the hello description'))
    opt.group('build').add(IntOption('foo', 'Allows specifying a number foo'))
    opt.add(ArgumentOption('argopt', 'Specifies an argument'))
    opt.add(FlagOption('foobar', 'Defines whether to foobar or not'))
    opt.add(EnableOption('something', 'Specifies whether something should be enabled'))


handler_called = False


def handle_options(opt):
    assert isinstance(opt, OptionHandler)
    assert ctx.options['foobar'].value
    global handler_called
    handler_called = True


def build_fun():
    pass


def test_options():
    setup_context()
    decorators._other.clear()
    decorators.options = options_fun
    decorators.handle_options = handle_options
    assert decorators.options == [options_fun]
    decorators.commands = Command('build', build_fun)
    for com in decorators.commands:
        ctx.commands.add(com)
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
    handler.handle_options()
    assert handler_called


def options_fun2(opt):
    opt.add(FlagOption('something', '', prefix=['-', '--'], keys=['foo', 'bar']))


def test_options2():
    setup_context()
    decorators._other.clear()
    decorators.options = options_fun2
    decorators.commands = Command('build', build_fun)
    for com in decorators.commands:
        ctx.commands.add(com)
    handler = OptionHandler()
    handler.parse(['-foo', '--bar', 'build'])
    assert handler.commands == ['build']
    assert ctx.options['something'].value


def empty_command_handler():
    pass


class TestTask(Task):
    pass


def task_yielder():
    yield TestTask()
    yield TestTask()
    yield TestTask()


def return_task():
    return [TestTask(), TestTask()]


def test_retrieve_commands():
    setup_context()
    decorators._other.clear()
    # emulate the decorator
    command('empty')(empty_command_handler)
    command('yield')(task_yielder)
    command('return')(return_task)
    for com in decorators.commands:
        ctx.commands.add(com)
    tasks = retrieve_command_tasks('empty')
    assert len(tasks) == 0
    try:
        retrieve_command_tasks('not-existing')
        assert False
    except NoSuchCommandError:
        pass
    tasks = retrieve_command_tasks('yield')
    test_tasks = []
    for t in tasks.values():
        if isinstance(t, TestTask):
            test_tasks.append(t)
    assert len(test_tasks) == 3
    tasks = retrieve_command_tasks('return')
    test_tasks = []
    for t in tasks.values():
        if isinstance(t, TestTask):
            test_tasks.append(t)
    assert len(test_tasks) == 2


if __name__ == '__main__':
    test_options()
    test_retrieve_commands()
