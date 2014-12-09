from .task import Task
from .util import EventLoop, Event, is_iterable

from threading import Thread


# TODO: task timeouts -> kill hanging tasks


class DependencyCycleError(Exception):
    pass


class RunnableTaskContainer(object):
    def __init__(self, task):
        self._dependencies = []
        self._task = task

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def task(self):
        return self._task

    def runnable(self):
        for dep in self._dependencies:
            if not dep.task.has_run:
                return False
        return True

    def finished(self):
        return self._task.has_run


class DAG(object):
    def __init__(self, tasks):
        self._tasks = []
        self._target_map = {}
        self.insert(tasks)
        self._runnable_tasks = []
        self._waiting_tasks = tasks
        self._executing_tasks = []

    def update_runnable(self):
        self._runnable_tasks = list(filter(lambda task: task.runnable() and not task.finished(), self._waiting_tasks))
        self._waiting_tasks = list(filter(lambda task: not task.runnable(), self._waiting_tasks))

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
        task.task.has_run = True
        self._executing_tasks.remove(task)

    def insert(self, tasks):
        self._tasks.extend(tasks)
        # n = number of tasks, m = average number of source nodes per task
        # p = average number of tasks producing a target
        # create map from target => task --> O(m*n)
        for task in tasks:
            for target in task.task.targets:
                if target.identifier not in self._target_map:
                    self._target_map[target.identifier] = []
                self._target_map[target.identifier].append(task)
        # add dependencies to every task, i.e. add all tasks producing each target --> O(m*n*p)
        for task in tasks:
            for source in task.task.sources:
                if source.identifier in self._target_map.keys():
                    additional_deps = self._target_map[source.identifier]
                    task.dependencies.extend(additional_deps)

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
        spawned = task.task.spawn()
        if spawned is not None:
            if is_iterable(spawned):
                self._dag.insert(list(spawned))
            else:
                self._dag.insert([spawned])
        if self._cancel:
            if self._current_jobs == 0:
                # no jobs running anymore, so quit the loop
                self._loop.cancel()
            return
        self.start()

    def start(self):
        while self._current_jobs < self._jobs:
            if self._dag.has_finished():
                self._loop.cancel()
                break
            # attempt to start new task
            task = self._dag.pop_runnable_task()
            if task is None:
                self._loop.cancel()
                break
            # TODO: use a thread-pool
            callable_ = lambda: run_task(task, self._success_event, self._failed_event)
            thread = Thread(target=callable_)
            task.task.check()
            thread.start()
            self._current_jobs += 1

    def cancel(self):
        self._cancel = True


def execute(tasks, jobs=1):
    tasks = flatten(tasks.values())
    if len(tasks) == 0:
        return
    dag = DAG(tasks)
    loop = EventLoop()
    executor = Executor(dag, loop, jobs=jobs)
    executor.start()
    loop.run()


def run_task(task, success_event=None, failed_event=None):
    real_task = task.task
    real_task.prepare()
    real_task.run()
    if real_task.success:
        real_task.on_success()
    else:
        real_task.on_fail()
    real_task.postprocess()
    if not real_task.success and failed_event is not None:
        failed_event.fire(task)
    elif success_event is not None:
        success_event.fire(task)
    for node in real_task.targets:
        node.signature.refresh()


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