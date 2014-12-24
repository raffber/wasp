from wasp import File, group, shell, tool, Directory, Argument, EnableOption, value, arg
import wasp
from wasp import ArgumentCollection

d = tool('d')
current_dir = Directory(__file__)


@wasp.build
def build():
    f = File('notes')
    cp = shell('cp {CPFLAGS} {SRC} {TGT}',
               sources=f, targets=f.to_builddir()
               ).use(cpflags='-r')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    return cp, group(one, two, link).use(dc='/usr/bin/dmd')


@wasp.options
def test_options(col):
    col.group('test').add(EnableOption('asdf', 'Enable or disable asdf', value=True))


@wasp.command('test')
def test():
    col = ArgumentCollection.load('test.json')
    for k, v in col.items():
        print('{0}: {1}'.format(k, v.value))

@wasp.task('test')
def _task_injection():
    print('asdf')


@wasp.command('md')
def md():
    mds = current_dir.glob('*.md')
    return [wasp.shell('markdown {SRC} > {TGT}', sources=md,
                       targets=md.to_builddir().replace_extension('html'))
            for md in wasp.files(mds)]
