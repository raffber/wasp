#!/usr/bin/env python3
# encoding: UTF-8
"""
This code is public domain.

This script unpacks the wasp build tool and should be checked into vcs
repositories.
"""

# PYTHON_ARGCOMPLETE_OK

import json
import sys
import os
import zlib
import binascii

UNPACK_DIR = '.wasp'
CACHE_FILE = 'c4che.json'

def detect_topdir():
    dir = os.getcwd()
    for f in os.listdir(dir):
        if f == CACHE_FILE:
            with open(f, 'r') as fobj:
                try:
                    d = json.load(fobj)
                except:
                    break
                ctx = d.get('ctx', None)
                if ctx is None:
                    break
                if not isinstance(ctx, dict):
                    break
                topdir = ctx.get('topdir', None)
                return topdir
    while dir != '/':
        for f in os.listdir(dir):
            if f == 'wasp':
                return dir
        dir = os.path.abspath(os.path.join(dir, '..'))
    return None


def main():
    topdir = detect_topdir()
    if topdir is None:
        print('Could not locate topdir. You must run ``gloabl-wasp`` '
              'either from a file tree'
              'containing a ``wasp`` file or from a build directory '
              'containing an initialized `{0}` file.'.format(CACHE_FILE))
        sys.exit(1)
    unpack_dir = os.path.join(topdir, UNPACK_DIR)
    if not os.path.exists(unpack_dir):
        fname = os.path.join(topdir, 'wasp')
        code = []
        with open(fname, 'r') as f:
            start = False
            for line in f:
                if 'wasp_packed=[' in line:
                    start = True
                if line == '\n' and start:
                    break
                if start:
                    code.append(line)
        vs = {}
        exec(''.join(code), vs, vs)
        unpack(unpack_dir, vs['wasp_packed'])
    sys.path.append(unpack_dir)
    run(topdir, unpack_dir)


class WaspInstallationError(RuntimeError):
    def __init__(self, msg):
        super().__init__(msg)


def remove_recursive(path):
    """
    Recursively remove directory tree.
    """
    if not os.path.isdir(path):
        os.remove(path)
        return
    for subpath in os.listdir(path):
        remove_recursive(os.path.join(path, subpath))


def unpack(unpack_dir, code):
    """
    Unpacks this script into unpack_dir.
    Already existing files are removed.
    """
    # recursive remove existing install
    if os.path.exists(unpack_dir):
        remove_recursive(unpack_dir)
    os.mkdir(unpack_dir)
    for filename, content in code:
        dirname = os.path.dirname(filename)
        # check if a dir needs to be created
        if dirname != '':
            dirname = os.path.join(unpack_dir, dirname)
            if not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
        # decompress and write file
        fname = os.path.join(unpack_dir, filename)
        with open(fname, 'w') as f:
            compressed = binascii.a2b_base64(content)
            data = zlib.decompress(compressed)
            s = data.decode('UTF-8')
            f.write(s)


def run(topdir, unpack_dir):
    # make sure cwd is the directory in which the wasp script
    # is. Thus, topdir gets set to cwd.
    os.chdir(topdir)
    try:
        wasp = __import__('wasp')
    except ImportError:
        raise WaspInstallationError('Something went wrong during the installation. Does {0} directory with all wasp files exist?'.format(UNPACK_DIR))
    # run the main routine
    from wasp.main import run
    success = run(topdir)
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
