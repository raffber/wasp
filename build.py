import os
import zlib
import binascii
from wasp import File, group, shell, tool, ctx
from wasp.ext.watch import watch
import wasp
from wasp.fs import find_exe

d = tool('d')
sphinx = tool('sphinx')
latex = tool('latex')
node = tool('nodejs')


@wasp.command('configure')
def configure():
    yield node.find_npm()
    yield node.ensure('jsmin').produce(':has-jsmin')
    yield node.find_package_binary('jsmin', argprefix='jsmin').use(':has-jsmin').produce(':jsmin')


@wasp.command('nodejs', depends='configure')
def _nodejs():
    for f in ctx.topdir.glob('*.js'):
        yield shell('{jsmin} {SRC} > {TGT}', sources=f, targets=f.to_builddir()).use(':jsmin')


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
    yield find_exe('py.test', argprefix='pytest').produce(':pytest')
    yield shell('{pytest} tests').use(':pytest')


@wasp.build
def main():
    dc = d.find_dc().produce(':dc')
    f = File('notes')
    yield shell('cp {CPFLAGS} {SRC} {TGT}',
                sources=f, targets=f.to_builddir(), cwd='doc'
                ).use(cpflags='-r')
    one = d.compile('one.d')
    two = d.compile('two.d')
    link = d.link(one, two)
    yield group(one, two, link).use(dc)
    yield dc


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
