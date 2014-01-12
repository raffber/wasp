from .node import make_nodes, remove_duplicates
from uuid import uuid4 as uuid
from io import StringIO
from .util import run_command, Factory


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

    def run(self):
        raise NotImplementedError


class ShellTask(object):
    def __init__(self, sources=[], targets=[], children=[]):
        super().__init__(sources=sources, targets=targets, children=children)

    @property
    def cmd(self):
        raise NotImplementedError

    def finished(self, exit_code, out, err):
        pass

    def run(self):
        commandstring = self.cmd
        out = StringIO()
        err = StringIO()
        exit_code = run_command(commandstring, stdout=out, stderr=err)
        self.finished(exit_code, out.read(), err.read())


class TaskResult(object):
    def to_json(self):
        return None

    @staticmethod
    def from_json(self, d):
        assert('name' in d, 'Invalid json for TaskResult. Delete cache!')
        return task_result_factory.create(d['name'], **d)


task_result_factory = Factory(TaskResult)


class register_task(object):
    def __init__(self):
        pass

    def __call__(self, cls):
        task_result_factory.register(cls)
        return cls