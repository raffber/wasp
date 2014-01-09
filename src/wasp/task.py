
from .node import make_nodes, remove_duplicates
from uuid import uuid4 as uuid
from .context import ctx

class Task(object):

    def __init__(self, sources=[], targets=[], children=[]):
        self._sources = make_nodes(sources)
        self._targets = make_nodes(targets)
        assert(isinstance(children, list))
        self.children = children
        self._id = uuid()

    @property
    def sources(self):
        ret = []
        for task in self.children:
            ret.extend(task.sources)
        ret.extend(self._sources)
        return remove_duplicates(ret)

    def __eq__(self, other):
        return other.identfier == self._id

    def __ne__(self, other):
        return not (other.identfier == self._id)

    @property
    def targets(self):
        ret = []
        for task in self.children:
            ret.extend(task.targets)
        ret.extend(self._targets)
        return remove_duplicates(ret)

    @property
    def identifier(self):
        return self._id


class ShellTask(object):
    pass