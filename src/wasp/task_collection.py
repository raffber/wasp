from .util import is_iterable


class TaskCollection(dict):

    def __init__(self, *tasks):
        super().__init__()
        for task in tasks:
            if task is None:
                continue
            if is_iterable(task):
                for t in task:
                    self.add(t)
            else:
                self.add(task)

    def add(self, task):
        if is_iterable(task):
            for t in task:
                self.add(t)
        else:
            self[task.identifier] = task

