import os

from wasp.config import Config


VALID_CONFIG = {
    'extensions': ['daemon'],
    'metadata': {
        'projectname': 'Wasp',
        'projectid': 'wasp',
        'some-other-key': 'foo'
    },
    'arguments' : {
        'string-arg': 'somevalue',
        'list-arg': ['asdf', 2, 3],
        'dict-arg': {
            'foo': 'bar'
        }
    },
    'pythonpath': '~/.local',
    'verbosity': 'debug',
    'default_command': 'build',
    'pretty': False,
}


def test_valid_config():
    conf = Config(VALID_CONFIG)
    assert conf.extensions == {'daemon'}
    meta = conf.metadata
    assert meta.projectname == 'Wasp'
    assert meta.projectid == 'wasp'
    assert meta.get('some-other-key') == 'foo'
    meta.set('some-other-key', 'bar')
    assert meta.get('some-other-key') == 'bar'
    argcol = conf.arguments
    assert argcol['string-arg'].value == 'somevalue'
    assert argcol['list-arg'].value == ['asdf', 2, 3]
    assert argcol['dict-arg'].value == {
        'foo': 'bar'
    }
    assert conf.pythonpath[0].path == os.path.expanduser('~/.local')
    assert conf.default_command == 'build'
    assert not conf.pretty
    assert conf.verbosity == 5

# TODO: test merge_* function

UNKNOWN_KEY = {
    'unknown_key': 'asdf'
}

INVALID_ARGS = {
    'arguments': [1, 2, 3]
}

INVALID_PYTHONPATH = {
    'pythonpath': True
}

INVALID_VERBOSITY = {
    'verbosity': 'foobar'
}

INVALID_PRETTY = {
    'verbosity': 'asdf'
}

INVALID_DEFAULT_COMMAND = {
    'default_command': []
}


def test_invalid_config():
    for data in [UNKNOWN_KEY, INVALID_ARGS, INVALID_PYTHONPATH,
                 INVALID_VERBOSITY, INVALID_PRETTY,
                 INVALID_DEFAULT_COMMAND]:
        try:
            Config(data)
            failed = False
        except ValueError:
            failed = True
        assert failed
