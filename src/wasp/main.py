from .util import load_module_by_path
from .decorators import decorators
from .context import Context
import wasp


def run_file(fpath):
    load_module_by_path(fpath)
    context = decorators.create_context()
    assert isinstance(context, Context), 'create_context: You really need to provide a subclass of wasp.Context'
    object.__setattr__(wasp.ctx, "_obj", context)
    for hook in decorators.init:
        hook()
    print('DONE')
