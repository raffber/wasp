from .task import Task, TaskGroup
from .util import EventLoop, Event, is_iterable
from . import log, old_signatures
from .task_collection import TaskCollection

from threading import Thread


# TODO: task timeouts -> kill hanging tasks


class DependencyCycleError(Exception):
    pass


class TaskContainer(object):
    def __init__(self, task):
        self._dependencies = []
        self._task = task
        self._frozen = False
        self._noop = None
        self._runnable = None
        self._has_run = None
        self._finished = False

    def freeze(self):
        self._frozen = True

    def thaw(self):
        self._noop = None
        self._has_run = None
        self._runnable = None
        self._frozen = False

    @property
    def noop(self):
        if self._frozen and self._noop is not None:
            return self._noop
        elif self._frozen:
            self._noop = self._test_noop()
            return self._noop
        return self._test_noop()

    def _test_noop(self):
        return len(self._task.run) == 1 and type(self._task)._run == Task._run

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def task(self):
        return self._task

    @property
    def has_run(self):
        if self._frozen and self._has_run is not None:
            return self._has_run
        elif self._frozen:
            self._has_run = self._task.has_run
            return self._has_run
        return self._task.has_run

    @property
    def runnable(self):
        if self._frozen and self._runnable is not None:
            return self._runnable
        elif self._frozen:
            self._runnable = self._test_runnable()
            return self._runnable
        return self._test_runnable()

    def _test_runnable(self):
        for dep in self._dependencies:
            if not dep.has_run:
                return False
        return True

    def __repr__(self):
        return repr(self.task)


class DAG(object):
    def __init__(self, tasks, produce=None):
        self._tasks = []
        self._target_map = {}
        self.insert(tasks)
        self._runnable_tasks = []
        self._executing_tasks = []
        if produce is not None:
            limited_set = set()
            produce_ids = [p.identifier for p in produce]
            required = []
            for task in tasks:
                if isinstance(task.task, TaskGroup):
                    targets = set(task.task.targets) - set(task.task.grouped_targets)
                else:
                    targets = task.task.targets
                for t in targets:
                    if t.identifier in produce_ids:
                        required.append(task)
            for req in required:
                limited = self._limit_selection(req)
                limited_set.add(req)
                for x in limited:
                    limited_set.add(x)
            self._waiting_tasks = [x for x in limited_set]
        else:
            self._waiting_tasks = tasks

    def _limit_selection(self, required_task):
        required = []
        for dep in required_task.dependencies:
            required.append(dep)
            required.extend(self._limit_selection(dep))
        return required

    def update_runnable(self):
        for task in self._waiting_tasks:
            task.freeze()
        self._runnable_tasks = []
        new_waiting_tasks = []
        for task in self._waiting_tasks:
            if task.runnable and not task.has_run:
                self._runnable_tasks.append(task)
            elif not task.runnable:
                new_waiting_tasks.append(task)
        self._waiting_tasks = new_waiting_tasks
        for task in self._waiting_tasks:
            task.thaw()
        for task in self._runnable_tasks:
            task.thaw()

    def pop_runnable_task(self):
        if len(self._runnable_tasks) == 0 and len(self._waiting_tasks) == 0:
            return None  # Done
        if len(self._runnable_tasks) == 0:
            self.update_runnable()
            if len(self._runnable_tasks) == 0 and len(self._executing_tasks) == 0 and len(self._waiting_tasks) != 0:
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
        self._consumed_nodes = []
        self._produced_nodes = []
        self._executed_tasks = TaskCollection()

    @property
    def executed_tasks(self):
        return self._executed_tasks

    @property
    def produced_nodes(self):
        return self._produced_nodes

    @property
    def consumed_nodes(self):
        return self._consumed_nodes

    def task_failed(self, task):
        self.cancel()
        self._current_jobs -= 1
        if self._current_jobs == 0:
            # no jobs running anymore, so quit the loop
            self._loop.cancel()
        # invalidate the sources, such that this task is rerun
        for source in task.task.sources:
            source.signature.invalidate()

    def task_success(self, task, start=True):
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
        self._consumed_nodes.extend(task.task.sources)
        self._produced_nodes.extend(task.task.targets)
        if start:
            self.start()

    def start(self):
        while self._current_jobs < self._jobs:
            if not self._loop.running and self._loop.started:
                break
            if self._dag.has_finished():
                self._loop.cancel()
                break
            # attempt to start new task
            task = self._dag.pop_runnable_task()
            # run them without a separate thread
            # due to overhead
            while task is not None and task.noop:
                self._current_jobs += 1
                self._executed_tasks.add(task)
                run_task(task)
                if task.success:
                    self.task_success(task, start=False)
                else:
                    self.task_failed(task)
                task = self._dag.pop_runnable_task()
            if task is None:
                self._loop.cancel()
                break
            self._executed_tasks.add(task)
            # TODO: use a thread-pool
            callable_ = lambda: run_task(task, self._success_event, self._failed_event)
            thread = Thread(target=callable_)
            task.task.check()
            thread.start()
            self._current_jobs += 1

    def cancel(self):
        self._cancel = True


def preprocess(tasks):
    for task in tasks:
        real_task = task.task
        real_task.log.configure(verbosity=log.verbosity)
        # if this would not be the case, the task would never be executed
        if len(real_task.sources) == 0 and len(real_task.targets) == 0:
            real_task.always = True


def execute(tasks, jobs=1, produce=None):
    tasks = flatten(tasks.values())
    if len(tasks) == 0:
        return TaskCollection()
    preprocess(tasks)
    dag = DAG(tasks, produce=produce)
    loop = EventLoop()
    executor = Executor(dag, loop, jobs=jobs)
    executor.start()
    if not loop.run():
        executor.cancel()
    # during execution, nodes have been consumed and produced. Thus, if new tasks should be processed
    # which consume or produce the same nodes, these tasks need to see the updated signatures of these
    # nodes to determine if they need to be run again.
    # TODO: refactor this into executor
    for node in executor.consumed_nodes:
        old_signatures.update(node.signature.identifier, node.signature)
    for node in executor.produced_nodes:
        old_signatures.update(node.signature.identifier, node.signature)
    return executor.executed_tasks


def run_task(task, success_event=None, failed_event=None):
    real_task = task.task
    real_task.prepare()
    real_task.run()
    if real_task.success:
        real_task.on_success()
    else:
        real_task.on_fail()
    real_task.postprocess()
    for node in real_task.targets:
        node.signature.refresh()
    if not real_task.success and failed_event is not None:
        failed_event.fire(task)
    elif success_event is not None:
        success_event.fire(task)


def flatten(tasks):
    ret = []
    for task in tasks:
        if isinstance(task, Task):
            task = TaskContainer(task)
        ret.append(task)
        dependencies = flatten(task.task.children)
        task.dependencies.extend(dependencies)
        ret.extend(dependencies)
    return ret