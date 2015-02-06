import os
import zlib
import binascii
from wasp import File, group, shell, tool, ctx, configure, chain, Directory
from wasp.ext.watch import watch
import wasp
from wasp.fs import find_exe

d = tool('d')
sphinx = tool('sphinx')
latex = tool('latex')
nodejs = tool('nodejs')
rust = tool('rust')


@configure
def configure():
    c = chain()
    c += nodejs.install('jsmin')
    c += nodejs.find_exe('jsmin').produce(':jsmin')
    yield c


@wasp.command('rust')
def _rust():
    return rust.executable('rust_test/main.rs', 'main')


@wasp.command('nodejs', depends='configure')
def _nodejs():
    for f in ctx.topdir.glob('.*?.js$', exclude='build/.*'):
        yield shell('{jsmin} {SRC} > {TGT}', sources=f, targets=f.to_builddir()).use(':jsmin')


@wasp.command('doc', description='Build project documentation.')
def doc():
    return sphinx.html('doc')


@watch(dirs=['doc', 'src/wasp'], regexp='^[a-z-_]*\.(rst|py)$', command='watch-doc')
def autorebuild_doc():
    return doc()


@wasp.command('test', description='Run unit and integration tests.')
def test():
    yield find_exe('py.test', argprefix='pytest').produce(':pytest')
    yield shell('{pytest} tests').use(':pytest')


@wasp.build
def main():
    f = File('notes')
    yield shell('cp {CPFLAGS} {SRC} {TGT}',
                sources=f, targets=f.to_builddir(), cwd='doc'
                ).use(cpflags='-r')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    yield group(one, two, link)


def recursive_list(dirname):
    lst = [f for f in os.listdir(dirname)]
    ret = []
    for f in lst:
        absf = os.path.join(dirname, f)
        if os.path.isdir(absf):
            ret.extend(recursive_list(absf))
        else:
            ret.append(absf)
    return ret


def do_create_wasp(task, target):
    target = str(target)
    waspdir = 'src'
    v = wasp.version
    with open(target, 'a') as out:
        out.write('\n\nwasp_packed=[')
        for fpath in recursive_list(waspdir):
            ext = os.path.splitext(fpath)[1]
            if ext != '.py':
                continue
            relpath = os.path.relpath(fpath, start=waspdir)
            with open(fpath, 'rb') as f:
                data = f.read()
                data = zlib.compress(data)
                data = binascii.b2a_base64(data)
                out.write('\n("{0}", {1}),'.format(relpath, data))
        out.write('\n]\n')
        out.write("""

if __name__ == '__main__':
    main({major}, {minor}, {point})


""".format(major=v.major, minor=v.minor, point=v.point))


@wasp.command('create-wasp', description='Builds the wasp redistributable')
def create_wasp():
    dest = ctx.builddir.join('wasp')
    yield wasp.copy('dist/wasp-prebuild', ctx.builddir).produce(':wasp-copy')
    yield wasp.Task(targets=dest,
                    fun=lambda task: do_create_wasp(task, dest)
                    ).use(':wasp-copy', file=dest)
