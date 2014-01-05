import zlib

import sys, os
import struct


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

def main():
    dirname = os.path.dirname(sys.argv[0])
    dirname = os.path.abspath(dirname)
    waspdir = os.path.join(dirname, 'src')
    # TEST:...
    fname = os.path.join(waspdir, 'wasp/__init__.py')
    with open(fname, 'rb') as f:
        data = f.read()
        data = zlib.compress(data)
        data = ascii85encode(data)
        data = ascii85decode(data)
        data = zlib.decompress(data)
        print(data)

if __name__ == '__main__':
    main()
