import sys
import os

test_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.abspath(os.path.join(test_dir, '../src'))
sys.path.append(src_dir)

import wasp
from wasp.context import Context


def setup_context(meta=None, config=None, recurse_files=[], builddir='build'):
    wasp.ctx.__assign_object(Context(meta=meta, config=config
                                     , recurse_files=recurse_files, builddir=builddir))


def destroy_context():
    wasp.ctx.__assign_object(None)