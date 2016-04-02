from io import StringIO

from wasp.logging import Logger


def test_multiline_string():
    l = Logger()
    l.configure(Logger.WARN, pretty=True)
    assert l.verbosity == Logger.WARN
    assert l.pretty
    log_str = l.format_multiline_message('foo', 'bar', color='red', start='qwer', multiline='asdf')
    assert str(log_str) == 'qwerfoo\nasdfbar'
    l.configure(pretty=False)
    log_str = l.format_multiline_message('foo', 'bar', color='red', start='qwer', multiline='asdf')
    assert str(log_str) == 'foo\nbar'


def test_verbosity_level():
    io = StringIO()
    l = Logger(io=io)
    assert l.verbosity == Logger.WARN
    l.configure(verbosity=Logger.ERROR)
    l.error('asdf')
    assert io.getvalue() == 'asdf\n'
    l.info('foo')
    assert io.getvalue() == 'asdf\n'
    l.fatal('bar')
    assert io.getvalue() == 'asdf\nbar\n'
    l.debug('hello')
    assert io.getvalue() == 'asdf\nbar\n'
    l.warn('world')
    assert io.getvalue() == 'asdf\nbar\n'


if __name__ == '__main__':
    test_multiline_string()
    test_verbosity_level()

