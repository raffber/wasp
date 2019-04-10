import sys
import os
from wasp.fs import Directory
from wasp.main import init_context

test_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.abspath(os.path.join(test_dir, '../src'))
sys.path.append(src_dir)

import wasp


def setup_context():
    Directory(__file__).join('c4che.json').remove()
    wasp.ctx.__init__()
    init_context(Directory(__file__))
    return wasp.ctx
