import zlib
import sys, os
import shutil
import binascii


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


def main():
    dirname = os.path.dirname(sys.argv[0])
    dirname = os.path.realpath(dirname)
    waspdir = os.path.join(dirname, 'src')
    target = os.path.join(dirname, 'wasp-build')
    shutil.copy(os.path.join(dirname, 'wasp-prebuild'), target)
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
    main()


""")



if __name__ == '__main__':
    main()
