from wasp import File, group, shell, tool, Directory
import wasp

d = tool('d')
current_dir = Directory(__file__)


@wasp.command('doc', description='Build project documentation')
def doc():
    if wasp.osinfo.posix:
        make_task = shell('make html', cwd='doc', always=True)
    else:
        make_task = shell('make.bat html', cwd='doc', always=True)
    return make_task


@wasp.build
def main():
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
               sources=f, targets=f.to_builddir()
               ).use(cpflags='-r')
    one = d.compile('one.d').produce(':one')
    two = d.compile('two.d').use(':one')
    link = d.link(one, two)
    return cp, group(one, two, link).use(dc='/usr/bin/dmd')
