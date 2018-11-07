import traceback
from multiprocessing import cpu_count

from wasp import Logger
from .node import SpawningNode, Node
from .task import Task, TaskGroup, MissingArgumentError, TaskCollection, TaskFailedError
from .util import EventLoop, Event, is_iterable, ThreadPool
from . import log, ctx, extensions

# TODO: task timeouts -> kill hanging tasks


class DependencyCycleError(Exception):
    """
    Raised if a dependency cycle between tasks is detected.
    """
    pass


class InvalidTaskDependencies(Exception):
    """
    Raised if a target is produced by multiple tasks.
    """
    pass


class TaskGraph(object):

    def __init__(self, tasks, ns=None):
        self._target_map = {}
        self._source_map = {}
        self._tasks = []
        self._nodes = {}
        self._leafs = set()
        self._ns = ns
        self.add_tasks(tasks)
        self._running_tasks = []

    def add_tasks(self, tasks):
        for t in tasks:
            assert isinstance(t, Task)
            self._tasks.append(t)
            for target in t.targets:
                if target.key in self._target_map:
                    raise InvalidTaskDependencies()
                self._target_map[target.key] = t
                if target.key in self._nodes:
                    continue
                target.invalidate()
                self._nodes[target.key] = target
            for source in t.sources:
                if source.key not in self._source_map:
                    self._source_map[source.key] = []
                self._source_map[source.key].append(t)
                if source.key in self._nodes:
                    continue
                source.invalidate()
                self._nodes[source.key] = source
        self._leafs = set(self._nodes.keys()) - set(self._target_map.keys())

    def start(self):
        self.referesh_leafs()

    def pop(self):
        ret = None
        toremove = []
        for task in self._tasks:
            source_keys = [n.key for n in task.sources]
            only_leafs = all(sk in self._leafs for sk in source_keys)
            if not only_leafs:
                continue
            if len(task.sources) == 0 or task.always:
                ret = task
                break
            for n in task.targets:
                assert isinstance(n, Node)
                # TODO: parallelize and lock
                if n.has_changed(ns=self._ns):
                    ret = task  # found a task to run
                    break
            if ret is not None:
                break
            # task is runnable
            for n in task.sources:
                assert isinstance(n, Node)
                # TODO: parallelize and lock
                if n.has_changed(ns=self._ns):
                    ret = task  # found a task to run
                    break
            if ret is not None:
                break
            # task does not need to be re-run
            toremove.append(task)
        for rm in toremove:
            self.task_completed(rm)
        if ret is not None:
            self._tasks.remove(ret)
            self._running_tasks.append(ret)
        if ret is None and len(self._running_tasks) == 0 and len(self._tasks) != 0:
            raise DependencyCycleError()
        return ret

    def task_completed(self, task):
        if task in self._running_tasks:
            self._running_tasks.remove(task)
        spawned = task.spawn()
        if spawned is not None:
            self.add_tasks(spawned)
        # remove all source that are not sources to other tasks
        for s in task.sources:
            src_tasks = self._source_map[s.key]
            assert isinstance(src_tasks, list)
            src_tasks.remove(task)
            if len(src_tasks) == 0:
                # node is not a source of any other task
                del self._nodes[s.key]
        # promote all targets to leafs
        self._leafs = self._leafs.union(set(tgt.key for tgt in task.targets))
        # remove these nodes from the target_map
        for tgt in task.targets:
            del self._target_map[tgt.key]
        # start running refresh on all leafs
        self.referesh_leafs()

    def referesh_leafs(self):
        # TODO: async
        for leaf_key in self._leafs:
            n = self._nodes[leaf_key]
            _ = n.signature()


class Executor(object):
    def __init__(self, ns=None):
        self._ns = ns
        self._graph = None
        self._log = Logger()

    def setup(self, graph):
        self._graph = graph

    def run(self):
        assert self._graph is not None
        while True:
            task = self._graph.pop()
            if task is None:
                break
            task.log = self._log
            try:
                task.check()
            except MissingArgumentError as e:
                msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                    '{0}: {1}'.format(type(e).__name__,  str(e)))
                self._log.fatal(msg)
                # self.task_failed(task)
                break
            run_task(task, self._ns)
            self._graph.task_completed(task)

    @property
    def executed_tasks(self):
        # TODO: ...
        return []

    @property
    def success(self):
        # TODO: ...
        return True


def execute(tasks, executor, produce=None, ns=None):
    """
    Runs a list of tasks using an executor.

    :param tasks: Dict like object containing the tasks to be executed.
    :param executor: The executor object to be used. If None, a :class:`ParallelExecutor`
        will be created.
    :param produce: A list of nodes. The tasks to be executed are limited such that only the
        the given nodes are produced (and all intermediate nodes).
    :param ns: The namespace in which the tasks should be executed. See :class:`wasp.signature.Signature`
        for more information on namespaces.
    """
    oldns = ctx.current_namespace
    ctx.current_namespace = ns
    tasks = _flatten(tasks.values(), ns=ns)
    if len(tasks) == 0:
        return TaskCollection()
    dag = TaskGraph(tasks, ns=ns)  # TODO: , produce=produce)
    if executor is None:
        executor = Executor(ns=ns)
    assert isinstance(executor, Executor)
    executor.setup(dag)
    extensions.api.tasks_execution_started(tasks, executor, dag)
    executor.run()
    extensions.api.tasks_execution_finished(tasks, executor, dag)
    ctx.current_namespace = oldns
    return executor.executed_tasks


def run_task(task, ns):
    """
    Runs a task and logs its result.

    :param task: A :class:`ExeTask` to be executed.
    """
    ret = extensions.api.run_task(task)
    if ret != NotImplemented:
        return ret
    extensions.api.task_started(task)
    for target in task.targets:
        target.before_run(target=True)
    for source in task.sources:
        source.before_run(target=False)
    try:
        task.prepare()
        task.run()
        if task.success:
            task.on_success()
        else:
            task.on_fail()
            log.debug(log.format_fail('Task `{}` failed'.format(type(task).__name__)))
        task.postprocess()
    except TaskFailedError as e:
        task.success = False
        log.fatal(str(e))
    except Exception as e:
        msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                '{0}: {1}'.format(type(e).__name__,  str(e)))
        log.fatal(msg)
        task.success = False
    if task.success:
        for node in task.targets:
            node.signature(ns).refresh()
    for target in task.targets:
        target.after_run(target=True)
    for source in task.sources:
        source.after_run(target=False)
    extensions.api.task_finished(task)
    return task.success


def _uniquify(node_list):
    """
    Uniquifies a list of nodes and returns a new list
    with only unique nodes.
    """
    ret = {}
    for x in node_list:
        ret[x.name] = x
    return ret.values()


def _flatten(tasks, ns=None):
    """
    Flattens a list of task objects.

    :param tasks: The tasks to be flattened.
    :param ns: The namespace in which the tasks are run.
    :return: Returns a flattened list of tasks, removing all TaskGroup() objects.
    """
    if not is_iterable(tasks):
        tasks = [tasks]
    ret = []
    for task in tasks:
        if isinstance(task, TaskGroup):
            ret.extend(_flatten(task.tasks, ns=ns))
        else:
            new_sources = _uniquify(task.sources)
            task.sources.clear()
            task.sources.extend(new_sources)
            new_targets = _uniquify(task.targets)
            task.targets.clear()
            task.targets.extend(new_targets)
            ret.append(task)
    return ret

