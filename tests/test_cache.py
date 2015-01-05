from wasp.cache import Cache
from wasp.fs import File
from . import test_dir

import os


def test_cache():
    os.chdir(os.path.abspath(os.path.join(test_dir, 'cache')))
    cache = Cache(File('cache.json'))
    cache.prefix('test')['foo'] = File('test')
    cache.save()
    cache.load()
    f = cache.prefix('test')['foo']
    assert isinstance(f, File)
    assert f.path == 'test'


