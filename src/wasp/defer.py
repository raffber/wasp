from .util import Serializable
from . import ctx


class DeferredTaskCollection(dict):

    def load(self, cache):
        pass

    def save(self, cache):
        pass


def defer(command_name, task):
    assert isinstance(task, Serializable), 'Task must be serializable if it should be deferred to another command.'
    ctx.deffered(command_name).add(task)
