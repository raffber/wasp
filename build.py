from wasp import File, group, shell, tool, Directory
import wasp
#from wasp.ext.watch import watch

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


#@watch(regexp='[^\.]*?\.md$', directory='.', command='md')
#def files_changed():
#    t = wasp.Task(always=True, fun=lambda: print('YAY!'))
    #print('MD files changed, markdowning them!')
    #return t

@wasp.command('md')
def md():
    mds = current_dir.glob('*.md')
    return [wasp.shell('markdown {SRC} > {TGT}', sources=md,
                       targets=md.to_builddir().replace_extension('html'))
            for md in wasp.files(mds)]
