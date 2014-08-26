from .task import Task


class TaskCollection(dict):

    def __init__(self, traits=[]):
        self._traits = traits

    def add(self, task):
        if isinstance(task, Task):
            for trait in self._traits:
                assert isinstance(task, trait), 'task must have trait: {0}'.format(trait.__name__)
            self[task.identifier] = task
        elif isinstance(task, list):
            for t in task:
                self.add(t)
        else:
            assert False, 'Either a list of task or task is required as argument'

