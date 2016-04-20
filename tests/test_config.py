import os

from wasp.config import Config


VALID_CONFIG = {
    'extensions': ['daemon'],
    'metadata': {
        'projectname': 'Wasp',
        'projectid': 'wasp',
        'some_other_key': 'foo'
    },
    'arguments' : {
        'string_arg': 'somevalue',
        'list_arg': ['asdf', 2, 3],
        'dict_arg': {
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
    assert meta.get('some_other_key') == 'foo'
    meta.set('some_other_key', 'bar')
    assert meta.get('some_other_key') == 'bar'
    argcol = conf.arguments
    assert argcol['string_arg'].value == 'somevalue'
    assert argcol['list_arg'].value == ['asdf', 2, 3]
    assert argcol['dict_arg'].value == {
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
