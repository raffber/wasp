
from .node import make_nodes, remove_duplicates

class Task(object):

    def __init__(self, ctx, sources=[], targets=[], children=[]):
        self.ctx = ctx
        self._sources = make_nodes(sources)
        self._targets = make_nodes(targets)
        assert(isinstance(children, list))
        self.children = children

    def get_dependencies(self):
        pass

    @property
    def sources(self):
        ret = []
        for task in self.children:
            ret.extend(task.sources)
        ret.extend(self._sources)
        return remove_duplicates(ret)


    @property
    def targets(self):
        ret = []
        for task in self.children:
            ret.extend(task.targets)
        ret.extend(self._targets)
        return remove_duplicates(ret)
