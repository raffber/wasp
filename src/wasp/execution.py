from .task import Task
from .util import EventLoop, Event


# TODO: task timeouts -> kill hanging tasks


class DependencyCycleError(Exception):
    pass


class RunnableTaskContainer(object):
    def __init__(self, task):
        self._dependencies = []
        self._task = task
        self._finished = False

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def task(self):
        return self._task

    def runnable(self):
        for dep in self._dependencies:
            if not dep.task.has_run():
                return False
        return True

    def get_finished(self):
        return self._finished

    def set_finished(self, finished):
        self._finished = finished

    finished = property(get_finished, set_finished)


class DAG(object):
    def __init__(self, tasks):
        self._task = tasks
        # n = num task, m = average number of target nodes per task
        # TODO: create map from target => task --> O(m*n)
        # TODO: add dependencies to every task, i.e. add all tasks producing each target --> O(m*n)
        # TODO:
        self._runnable_tasks = []
        self._waiting_tasks = tasks
        self._executing_tasks = []

    def update_runnable(self):
        self._runnable_tasks = filter(lambda task: task.runnable(), self._waiting_tasks)
        self._waiting_tasks = filter(lambda task: not task.runnable(), self._waiting_tasks)

    def pop_runnable_task(self):
        if len(self._runnable_tasks) == 0 and len(self._waiting_tasks) == 0:
            return None  # Done
        if len(self._runnable_tasks) == 0:
            self.update_runnable()
            if len(self._runnable_tasks) == 0 and len(self._executing_tasks) == 0:
                raise DependencyCycleError('The task graph is not a DAG: Dependency cycle found!')
        if len(self._runnable_tasks) == 0:
            return None
        task = self._runnable_tasks.pop()
        self._executing_tasks.append(task)
        return task

    def task_finished(self, task):
        task.finished = True
        self._executing_tasks.remove(task)

    def has_finished(self):
        return len(self._runnable_tasks) == 0 and len(self._waiting_tasks) == 0 and len(self._executing_tasks) == 0


class Executor(object):
    def __init__(self, dag, loop, jobs=1):
        self._current_jobs = 0
        self._loop = loop
        self._jobs = jobs
        self._dag = dag
        self._cancel = False
        self._success_event = Event(self._loop).connect(self.task_success)
        self._failed_event = Event(self._loop).connect(self.task_failed)

    def task_failed(self, task):
        self.cancel()
        self._current_jobs -= 1
        if self._current_jobs == 0:
            # no jobs running anymore, so quit the loop
            self._loop.cancel()

    def task_success(self, task):
        self._current_jobs -= 1
        self._dag.task_finished(task)
        if self._cancel:
            if self._current_jobs == 0:
                # no jobs running anymore, so quit the loop
                self._loop.cancel()
            return
        self.start()

    def start(self):
        while self._current_jobs < self._jobs:
            # attempt to start new task
            task = self._dag.pop_runnable_task()
            # TODO: start new thread with task
            self._current_jobs += 1

    def cancel(self):
        self._cancel = True


def execute(tasks, jobs=1):
    tasks = flatten(tasks)
    dag = DAG(tasks)
    loop = EventLoop()
    executor = Executor()
    executor.start()
    loop.run()


def run_task(task, success_event=None, failed_event=None):
    # task.prepare()
    # task.initialize()
    # task.run()
    # task.
    if not task.task.success and failed_event is not None:
        failed_event.fire(task)
    elif success_event is not None:
        success_event.fire(task)


def flatten(tasks):
    ret = []
    for task in tasks:
        if isinstance(task, Task):
            task = RunnableTaskContainer(task)
        ret.append(task)
        dependencies = flatten(task.task.children)
        task.dependencies.extend(dependencies)
        ret.extend(dependencies)
    return ret