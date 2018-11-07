import os
import zlib
import binascii
from wasp.util import first
from wasp import shell, tool, ctx, recurse
import wasp
from wasp.fs import find_exe, Directory, files
from wasp.task import TaskFailedError

sphinx = tool('sphinx')

recurse('buildtest')


@wasp.command('doc', description='Build project documentation.')
def doc():
    return sphinx.html('doc')


@wasp.command('test', description='Run unit and integration tests.')
def test():
    yield find_exe('py.test', argprefix='pytest').produce(':pytest')
    yield shell('{pytest} tests').use(':pytest')


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


def do_create_wasp(t):
    source = first(files(t.sources, ignore=True))
    target = first(files(t.targets, ignore=True))
    if source is None or target is None:
        raise TaskFailedError('CreateWasp: source or target not given.')
    source.copy_to(target)
    waspdir = Directory('src')
    v = wasp.version
    with open(str(target), 'a') as out:
        out.write('\n\nwasp_packed=[')
        for f in waspdir.glob('.*\.py$', recursive=True):
            # replace \ with / on windows, otherwise string excaping
            # might not work
            relpath = os.path.relpath(f.path, start=waspdir.path).replace('\\', '/')
            with open(f.path, 'rb') as inf:
                data = inf.read().replace(b'\r\n', b'\n')
                data = zlib.compress(data)
                data = binascii.b2a_base64(data)
                out.write('\n("{0}", {1}),'.format(relpath, data))
        out.write('\n]\n')
        out.write("""

if __name__ == '__main__':
    main({major}, {minor}, {point})


""".format(major=v.major, minor=v.minor, point=v.point))
    t.log.info(t.log.format_success('Created wasp.'))


@wasp.command('create-wasp', description='Builds the wasp redistributable')
def create_wasp():
    return wasp.Task(sources='dist/wasp-prebuild',
                     targets=ctx.builddir.join('wasp'),
                     fun=do_create_wasp, always=True)
