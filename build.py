from wasp import File, group, shell, tool, Directory
from wasp.ext.watch import watch
import wasp

d = tool('d')
sphinx = tool('sphinx')
current_dir = Directory(__file__)


@wasp.command('doc', description='Build project documentation.')
def doc():
    compiler = sphinx.find()
    html = sphinx.html('doc').use(compiler)
    return html, compiler
    # if wasp.osinfo.posix:
    #     make_task = shell('make html', cwd='doc', always=True)
    # else:
    #     make_task = shell('make.bat html', cwd='doc', always=True)
    # return make_task


@watch(directory='doc', regexp='^[a-z-_]*\.rst$')
def autorebuild_doc():
    return doc()


@wasp.command('test', description='Run unit and integration tests.')
def test():
    # pytest = find_exe('py.test', arg='exe')
    # sh = shell('{exe} tests').use(pytest)
    # return pytest, sh
    return shell('py.test tests')


@wasp.build
def main():
    dc = d.find_dc()
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
               sources=f, targets=f.to_builddir()
               ).use(cpflags='-r')
    one = d.compile('one.d').produce(':one')
    two = d.compile('two.d').use(':one')
    link = d.link(one, two)
    return cp, group(one, two, link).use(dc), dc
