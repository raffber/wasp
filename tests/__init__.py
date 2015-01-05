import sys
import os

test_dir = os.path.abspath(os.path.dirname(__file__))
src_dir = os.path.abspath(os.path.join(test_dir, '../src'))
sys.path.append(src_dir)

from wasp import Context, ctx


def setup_context():
    ctx.__assign_object(Context())