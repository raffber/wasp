from .util import EventLoop, Event
from threading import Thread
from . import ctx
from .task import Check


class TaskContainer(object):
    def __init__(self, task):
        self._dependencies = []
        self._parent = None
        self._task = task

    def set_parent(self, task):
        self._parent = task

    def get_parent(self):
        return self._parent

    parent = property(get_parent, set_parent)

    def add_dependency(self, dep):
        self._dependencies.append(dep)

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def runnable(self):
        for task in self._dependencies:
            if not task.has_run:
                return False
        return True

    @property
    def has_run(self):
        return self._task.has_run

    @property
    def task(self):
        return self._task

    @property
    def children(self):
        return self._task.children


class DependencyCycleError(Exception):
    pass


class RunnableDependencyTree(object):
    def __init__(self, tasks):
        self._tasks = [tasks[key] for key in tasks]
        self._flatten_task_list()
        self._exec_count = 0
        self._target_map = {}
        # build the target map such that we can quickly map
        # from target => task
        for task in self._tasks:
            for target in task.task.targets:
                lst = self._target_map.get(target.identifier, None)
                if lst is not None:
                    lst.append(task)
                else:
                    lst = [task]
                    self._target_map[target.identifier] = lst
        # go over all tasks and find for each source a task
        # that has this source as target
        for task in self._tasks:
            for source in task.task.sources:
                dependency_tasks = self._find_tasks_with_target(source)
                for dep in dependency_tasks:
                    task.add_dependency(dep)

    def task_finished(self, task):
        self._exec_count += 1

    @property
    def finished(self):
        task_left = []
        for task in self._tasks:
            if not task.has_run:
                task_left.append(task)
        return len(task_left) == 0

    def _recursive_flatten(self, task):
        task = TaskContainer(task)
        ret = [task]
        for c in task.task.children:
            task.add_dependency(c)
            ret.extend(self._recursive_flatten(c))
        return ret

    def _flatten_task_list(self):
        new_list = []
        for task in self._tasks:
            new_list.extend(self._recursive_flatten(task))
        self._tasks = new_list

    def _find_tasks_with_target(self, target):
        return self._target_map.get(target.identifier, [])

    def pop_runnable_task(self):
        if self.finished:
            return None
        for task in self._tasks:
            if task.has_run:
                self._tasks.remove(task)
            elif task.runnable:
                self._tasks.remove(task)
                return task.task
        # well crap... we got a dependency cycle
        # TODO: description
        raise DependencyCycleError('There is a cycle in your dependencies')


class TaskExecutor(Thread):
    def __init__(self, task, loop):
        super().__init__()
        self._task = task
        self._finished_event = Event(loop)

    @property
    def finished(self):
        return self._finished_event

    def run(self):
        self._task.run()
        self._finished_event.invoke(self._task)


class TaskExecutionPool(object):
    def __init__(self, dependency_tree, num_jobs=1):
        self._num_jobs = num_jobs
        self._tasks = dependency_tree
        self._loop = EventLoop()
        self._running_tasks = 0
        self._results = []

    def _start_next_task(self):
        task = self._tasks.pop_runnable_task()
        if task is None and self._running_tasks == 0:
            self._loop.cancel()
            return
        task.prepare()
        executor = TaskExecutor(task, self._loop)
        executor.finished.connect(self._on_task_finished)
        executor.start()
        self._running_tasks += 1

    def _on_task_finished(self, task):
        self._running_tasks -= 1
        self._start_next_task()
        self._tasks.task_finished(task)
        if not task.success:
            return
        result = task.result
        if result is None:
            return
        if isinstance(result, list):
            self._results.extend(result)
        else:
            self._results.extend(result)

    def run(self):
        for i in range(self._num_jobs):
            self._start_next_task()
        self._loop.run()
        return self._results