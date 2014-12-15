from .task import Task
from .util import is_iterable


# TODO: refactor, this became pointless, but build improved task collection api here


class TaskCollection(dict):

    def __init__(self, traits=None):
        if traits is None:
            traits = []
        self._traits = traits

    def add(self, task):
        if isinstance(task, Task):
            for trait in self._traits:
                assert isinstance(task, trait), 'task must have trait: {0}'.format(trait.__name__)
            self[task.identifier] = task
            return
        assert is_iterable(task), 'Either an iterable of task or task is' \
                                  ' required as argument, found: {0}'.format(type(task).__name__)
        # task is a list of Task
        for t in task:
            self.add(t)

