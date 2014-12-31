from wasp import File, group, shell, tool
from wasp.ext.watch import watch
import wasp
from wasp.fs import find_exe

d = tool('d')
sphinx = tool('sphinx')
latex = tool('latex')


@wasp.command('doc', description='Build project documentation.')
def doc():
    compiler = sphinx.find()
    html = sphinx.html('doc').use(compiler)
    return html, compiler


@watch(directory='doc', regexp='^[a-z-_]*\.rst$', command='watch-doc')
def autorebuild_doc():
    return doc()


@wasp.command('test', description='Run unit and integration tests.')
def test():
    pytest = find_exe('py.test', argprefix='pytest').produce(':pytest')
    return shell('{pytest} tests').use(':pytest'), pytest


@wasp.build
def main():
    dc = d.find_dc().produce(':dc')
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
               sources=f, targets=f.to_builddir(), cwd='doc'
               ).use(cpflags='-r')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    return cp, group(one, two, link).use(':dc'), dc


@wasp.command('create-wasp', description='Creates')
def create_wasp():
    pass