from wasp.cache import Cache
from wasp.fs import File
from . import test_dir

import os


def test_cache():
    os.chdir(os.path.abspath(test_dir))
    cache = Cache(File('cache/cache.json'))
    cache.prefix('test')['foo'] = File('test')
    cache.save()
    cache.load()
    f = cache.prefix('test')['foo']
    assert isinstance(f, File)
    assert f.path == 'test'


