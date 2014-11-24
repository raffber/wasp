from .util import Serializable
from . import ctx, register, factory


@register
class DeferredTaskCollection(dict, Serializable):

    def add(self, task):
        assert isinstance(task, Serializable), 'Task must be serializable if its execution should be deferrred'
        self[task.identifier] = task

    @classmethod
    def from_json(cls, d):
        self = cls()
        for k, v in d.items():
            if k == '__type__':
                continue
            self.add(factory.from_json(d[k]))
        return self

    def to_json(self):
        d = super().to_json()
        for task in self:
            assert isinstance(task, Serializable), 'Task must be serializable if its execution should be deferrred'
            d[task.identifier] = task.to_json()
        return d

    def save(self, cache):
        cache['deferred'] = self

    def load(self, cache):
        if not 'deferred' in cache:
            self.update(cache['deferred'])


def defer(command_name, task):
    assert isinstance(task, Serializable), 'Task must be serializable if its execution should be deferrred'
    ctx.deffered(command_name).add(task)
