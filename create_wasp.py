import zlib

import sys, os
import struct
import shutil
import binascii

def ascii85encode(data):
    result = ''
    i = 0
    while 1:
        buf = [int(x) for x in data[i:i+4]]
        i += len(buf)
        if not buf:
            break
        while i % 4:
            buf.append(0)
            i += 1
        num = (buf[0] << 24) + (buf[1] << 16) + (buf[2] << 8) + buf[3]
        if num == 0:
            result += 'z'
            continue
        res = [0, 0, 0, 0, 0]
        for j in (4, 3, 2, 1, 0):
            res[j] = ord('!') + num % 85
            num = num // 85
        res = res[:len(buf)+1]
        result = result + ''.join(map(chr, res))
    return result


def ascii85decode(data):
    n = b = 0
    out = b''
    for c in data:
        if '!' <= c and c <= 'u':
            n += 1
            b = b*85+(ord(c)-ord('!'))
            if n == 5:
                out += struct.pack('>L', b)
                n = b = 0
        elif c == 'z':
            assert n == 0
            out += '\0\0\0\0'
        elif c == '~':
            if n:
                for _ in range(5-n):
                    b = b*85+84
                out += struct.pack('>L', b)[:n-1]
            break
    return out

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
    dirname = os.path.abspath(dirname)
    waspdir = os.path.join(dirname, 'src')
    target = os.path.join(dirname, 'wasp')
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
