from util import b85encode

import sys, os


def main():
    dirname = os.path.dirname(sys.argv[0])
    dirname = os.path.abspath(dirname)
    dirname = os.path.abspath(os.path.join(dirname, '..'))
    waspdir = os.path.join(dirname, 'src')
    # TEST:...
    fname = os.path.join(waspdir, 'wasp/__init__.py')

if __name__ == '__main__':
    main()
