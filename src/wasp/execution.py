import multiprocessing.dummy
import traceback
from multiprocessing import cpu_count

from . import log, ctx, extensions
from .node import SpawningNode, Node, node
from .task import Task, TaskGroup, MissingArgumentError, TaskCollection, TaskFailedError
from .util import EventLoop, Event, is_iterable, ThreadPool


REFRESH_THREADS = 10
thread_pool = multiprocessing.dummy.Pool(REFRESH_THREADS)


# TODO: task timeouts -> kill hanging tasks
# TODO: limit selection to only a certain set of nodes


class DependencyCycleError(Exception):
    """
    Raised if a dependency cycle between tasks is detected.
    """
    pass


class TargetProducedByMultipleTasksError(Exception):
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
        self._produced_signatures = set()
        self._new_nodes = {}

    @property
    def produced_signatures(self):
        return self._produced_signatures

    def limit(self, target_nodes):
        pass

    def _scan_changes(self, task):
        nodes = list(task.sources)
        nodes.extend(task.targets)
        changes = thread_pool.map(lambda n: n.has_changed(self._ns), nodes)
        return any(changes)

    def _insert_task(self, t):
        assert isinstance(t, Task)
        if t.disabled:
            return
        self._tasks.append(t)
        for target in t.targets:
            if target.key in self._target_map:
                raise TargetProducedByMultipleTasksError()
            self._target_map[target.key] = t
            if target.key in self._nodes:
                continue
            self._nodes[target.key] = target
        for source in t.sources:
            if source.key not in self._source_map:
                self._source_map[source.key] = []
            self._source_map[source.key].append(t)
            if source.key in self._nodes:
                continue
            self._nodes[source.key] = source

    def add_tasks(self, tasks):
        for t in tasks:
            self._insert_task(t)
        # fetch all spawning nodes and let them spawn new tasks if there is no task
        # already producing this node
        spawning_nodes = [n for n in self._nodes.values() if isinstance(n, SpawningNode)]
        for n in spawning_nodes:
            sig = n.signature(ns=self._ns)
            if not sig.valid:
                sig.refresh()
            if sig.value is not None:
                continue
            if n.key not in self._target_map:
                spawned = n.spawn()
                if not is_iterable(spawned):
                    spawned = [spawned]
                for t in spawned:
                    self._insert_task(t)
        # compute the leaf nodes where we start our execution
        old_leafs = self._leafs
        self._leafs = set(self._nodes.keys()) - set(self._target_map.keys())
        # invalidate all leaf nodes that were added to ensure we refresh them
        # when we check for runnable tasks
        for leaf in self._leafs - old_leafs:
            self._nodes[leaf].invalidate()

    def _find_runnable(self):
        ret = None
        toremove = []
        for task in self._tasks:
            source_keys = [n.key for n in task.sources]
            only_leafs = all(sk in self._leafs for sk in source_keys)
            if not only_leafs:
                continue
            if (len(task.sources) == 0 and len(task.targets) == 0) or task.always:
                ret = task
                break
            # task is runnable
            if self._scan_changes(task):
                ret = task
                break
            # task does not need to be re-run
            toremove.append(task)
        return ret, toremove

    def pop(self):
        while True:
            ret, toremove = self._find_runnable()
            for rm in toremove:
                self._tasks.remove(rm)
                self.task_completed(rm, False)
            if ret is not None:
                self._tasks.remove(ret)
                self._running_tasks.append(ret)
                break  # we found a task, let's return it
            if len(toremove) == 0:
                break  # we didn't accomplish anything...
            # try to find a runnable task again
        if ret is None and len(self._running_tasks) == 0 and len(self._tasks) != 0:
            raise DependencyCycleError()
        return ret

    def task_completed(self, task, has_run):
        # TODO: inefficient
        if task in self._running_tasks:
            self._running_tasks.remove(task)
        spawned = task.spawn()
        if spawned is not None:
            if not is_iterable(spawned):
                spawned = [spawned]
            self.add_tasks(spawned)
        # remove all source that are not sources to other tasks
        for s in task.sources:
            src_tasks = self._source_map[s.key]
            assert isinstance(src_tasks, list)
            src_tasks.remove(task)
            self._produced_signatures.add(s.key)
            if len(src_tasks) == 0:
                # node is not a source of any other task
                del self._nodes[s.key]
                # thus also no leaf
                self._leafs.remove(s.key)
        # promote all targets to leafs
        touched = task.touched()
        new_leafs = set(tgt.key for tgt in touched)
        self._leafs = self._leafs | new_leafs
        # remove these nodes from the target_map
        for tgt in task.targets:
            self._produced_signatures.add(tgt.key)
            del self._target_map[tgt.key]
        # determine if there are new nodes to be inserted
        # into the database
        new_nodes = task.new_nodes
        if new_nodes is not None:
            if not is_iterable(new_nodes):
                new_nodes = [new_nodes]
            new_nodes = [node(x) for x in new_nodes]
            new_nodes = [n for n in new_nodes if n.key not in self._nodes]
            for n in new_nodes:
                self._new_nodes[n.key] = n
        if not has_run:
            return
        # referesh all node that were touched by the task
        for leaf in touched:
            leaf.signature(ns=self._ns).refresh()

    def post_run(self):
        # rescan all new nodes but only the ones which we didn't already produce
        new_nodes = set(self._new_nodes.keys()) - set(self._produced_signatures)
        for key in new_nodes:
            n = self._new_nodes[key]
            assert isinstance(n, Node)
            n.signature(ns=self._ns).refresh()

    @property
    def running_tasks(self):
        return self._running_tasks

    @property
    def completed(self):
        return len(self._tasks) == 0 and len(self._running_tasks) == 0


class Executor(object):
    def __init__(self, ns=None):
        self._ns = ns
        self._graph = None
        self._log = log.clone()
        self._success = True
        self._invalidate_nodes = []

    def setup(self, graph):
        self._graph = graph

    @property
    def success(self):
        return self._success

    def run(self):
        self._run()
        for node in self._invalidate_nodes:
            assert isinstance(node, Node)
            node.invalidate(ns=self._ns)

    def _run(self):
        raise NotImplementedError

    def cancel(self):
        raise NotImplementedError

    def _start(self):
        raise NotImplementedError

    def task_success(self, task, start=True):
        """
        Must be called if a task has finished successfully.
        """
        assert self._graph is not None, 'Call setup() first'
        self._graph.task_completed(task, True)
        spawned = task.spawn()
        if spawned is not None:
            self._graph.add_tasks(_flatten(spawned))
        if start:
            self._start()

    def task_failed(self, task):
        """
        Must be called if a task has failed.
        """
        self.cancel()
        self._success = False
        self._invalidate_nodes.extend(task.targets)

    def _post_run(self):
        self._graph.post_run()


class SingleThreadedExecutor(Executor):
    def __init__(self, ns=None):
        super().__init__(ns=ns)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _run(self):
        self._start()

    def _start(self):
        assert self._graph is not None
        while not self._cancel:
            task = self._graph.pop()
            if task is None:
                break
            if task.log is None:
                task.log = self._log
            try:
                task.check()
            except MissingArgumentError as e:
                msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                    '{0}: {1}'.format(type(e).__name__,  str(e)))
                self._log.fatal(msg)
                self._success = False
                break
            success = run_task(task, self._ns)
            if success:
                self.task_success(task, start=False)
            else:
                self.task_failed(task)
        self._post_run()


class ParallelExecutor(Executor):
    class TaskRunner(object):
        """
        Callable class for executing a task.
        :param task: The task to be executed.
        :param on_success: An :class:`wasp.util.Event` object called upon success.
        :param on_fail: A :class:`wasp.util.Event` object called upon failure.
        """

        def __init__(self, task, on_success, on_fail, ns):
            self._on_success = on_success
            self._on_fail = on_fail
            self._task = task
            self._ns = ns

        def __call__(self):
            try:
                succ = run_task(self._task, ns=self._ns)
                if not succ:
                    self._on_fail.fire(self._task)
                    return
                self._on_success.fire(self._task)
            except KeyboardInterrupt:
                log.fatal(log.format_fail('Execution Interrupted!!'))
                self._on_fail.fire(self._task)

    def __init__(self, ns=None, jobs=None):
        super().__init__(ns=ns)
        if jobs is None:
            jobs = cpu_count() * 2
        self._loop = EventLoop()
        self._success_event = Event(self._loop).connect(self.task_success)
        self._failed_event = Event(self._loop).connect(self.task_failed)
        self._startup_event = Event(self._loop).connect(self._start)
        self._thread_pool = ThreadPool(self._loop, jobs)
        self._loop.on_interrupt(self._thread_pool.cancel)
        self._thread_pool.on_finished(self._loop.cancel)
        self._loop.on_startup(self._start)
        self._cancel = False

    def cancel(self):
        self._thread_pool.cancel()
        self._cancel = True

    def _run(self):
        self._thread_pool.start()
        if not self._loop.run():
            log.log_fail('Execution Interrupted!!')
        self._post_run()

    def _start(self):
        assert self._graph is not None, 'Call setup() first'
        while True:
            if self._cancel:
                break
            if not self._loop.running and self._loop.started:
                break
            if self._graph.completed:
                self._thread_pool.cancel()
                break
            # attempt to start new task
            task = self._graph.pop()
            if task is None:
                if self._graph.completed:
                    self._thread_pool.cancel()
                break
            if task.log is None:
                task.log = self._log
            try:
                task.check()
            except MissingArgumentError as e:
                msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                                      '{0}: {1}'.format(type(e).__name__, str(e)))
                log.fatal(msg)
                self.task_failed(task)
                break
            runner = ParallelExecutor.TaskRunner(task, self._success_event, self._failed_event, self._ns)
            self._thread_pool.submit(runner)


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
        executor = SingleThreadedExecutor(ns=ns)
    assert isinstance(executor, Executor)
    executor.setup(dag)
    extensions.api.tasks_execution_started(tasks, executor, dag)
    executor.run()
    extensions.api.tasks_execution_finished(tasks, executor, dag)
    ctx.current_namespace = oldns


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
            node.signature(ns=ns).refresh()
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

