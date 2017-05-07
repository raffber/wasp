import os

import wasp
from bps.util import first
from wasp import copy, directory, file, factory
from wasp.fs import CopyTask
from wasp.generator import Generator, GeneratorCollection
from wasp.main import init_context, retrieve_command_tasks
from wasp import ctx


curdir = directory(__file__)


class DummyGenerator(Generator):

    key = 'foobar'

    def __init__(self, source=None, destination=None, restored=False):
        if source is not None:
            self.source = file(source)
        else:
            self.source = file(curdir.join('test-dir').join('test.txt'))
        if destination is not None:
            self.destination = file(destination)
        else:
            self.destination = self.source.append_extension('backup')
        self.restored = restored

    def run(self):
        yield copy(self.source, self.destination)

    def to_json(self):
        d = super().to_json()
        d['source'] = self.source.path
        d['destination'] = self.destination.path
        return d

    @classmethod
    def from_json(cls, d):
        ret = cls(source=d['source'], destination=d['destination'], restored=True)
        return ret


factory.register(DummyGenerator)


@wasp.command('generator-test')
def generator_test():
    pass


def test_generator():
    if curdir.join('test-dir').exists:
        curdir.join('test-dir').remove(recursive=True)
    testdir = curdir.mkdir('test-dir')
    with open(testdir.join('test.txt').path, 'w') as f:
        f.write('foobar')
    os.chdir(curdir.path)
    # startup
    init_context(testdir)
    # first stage - add generator
    generator = DummyGenerator()
    ctx.generators('generator-test').add(generator)
    # shutdown => save the context
    ctx.save()
    # restart => reload the context
    init_context(testdir)
    for com in wasp.decorators.commands:
        ctx.commands.add(com)
    # run the command
    tasks = retrieve_command_tasks('generator-test')
    assert isinstance(tasks[first(tasks)], CopyTask)
    generators = ctx.generators('generator-test')
    assert isinstance(generators, GeneratorCollection)
    assert isinstance(generators['foobar'], DummyGenerator)


if __name__ == '__main__':
    test_generator()
