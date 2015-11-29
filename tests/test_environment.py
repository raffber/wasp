from wasp.environment import Environment
import os


def test_environment():
    env = Environment()
    actualenv = dict(os.environ)
    argcol = env.argument_collection()
    for k, v in actualenv.items():
        assert env[k] == v
        assert argcol.value(k) == v
