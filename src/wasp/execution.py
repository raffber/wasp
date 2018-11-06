import traceback
from multiprocessing import cpu_count

from .node import SpawningNode
from .task import Task, TaskGroup, MissingArgumentError, TaskCollection, TaskFailedError
from .util import EventLoop, Event, is_iterable, ThreadPool
from . import log, ctx, extensions

# TODO: task timeouts -> kill hanging tasks


class DependencyCycleError(Exception):
    """
    Raised if a dependency cycle between tasks is detected.
    """
    pass


class TaskContainer(object):
    """
    Container object for a task. Allows caching several
    properties using the :meth:`freeze()` and :meth:`thaw()` methods.
    Once :meth:`freeze()` is called, the properties of the task are
    evaluated at most oncea and return values are cached. Caching is
    deactiavted again by calling :meth:`thaw()`.

    Also, the :class:`TaskContainer` keeps track of all dependencies of
    a task.
    """
    def __init__(self, task, ns=None):
        self._dependencies = []
        self._ns = ns
        self._task = task
        self._frozen = False
        self._noop = None
        self._runnable = None
        self._has_run = False
        self._finished = False
        self._nodes_changed = True
        # if this would not be the case, the task would never be executed
        if len(task.sources) == 0 and len(task.targets) == 0:
            task.always = True
        if task.log is None:
            task.log = log.clone()

    @property
    def targets(self):
        """
        Returns the nodes produced by the task.
        """
        return self._task.targets

    @property
    def sources(self):
        """
        Returns the nodes consumed by the task.
        """
        return self._task.sources

    def freeze(self):
        """
        Activates caching of some task properties. While the
        :class:`TaskContainer` is frozen, the properties are evaluated at
        most once their return value is cached.
        """
        self._frozen = True

    def thaw(self):
        """
        Deactivates caching.
        """
        self._noop = None
        self._runnable = None
        self._nodes_changed = None
        self._frozen = False

    @property
    def noop(self):
        """
        Returns True, if the task does not do anything.
        """
        if self._frozen and self._noop is not None:
            return self._noop
        elif self._frozen:
            self._noop = self._test_noop()
            return self._noop
        return self._test_noop()

    def _test_noop(self):
        return len(self._task.run) == 1 and type(self._task)._run == Task._run or self._task.noop

    @property
    def dependencies(self):
        """
        Returns a list of tasks which must be run before this task.
        """
        return self._dependencies

    @property
    def task(self):
        """
        Provides access to the actual :class:`Task` object.
        """
        return self._task

    @property
    def has_run(self):
        """
        Returns True if the task has already run successfully and does not
        need to be rerun again.
        """
        return self._has_run

    @has_run.setter
    def has_run(self, value):
        self._has_run = bool(value)

    def _test_nodes_changed(self):
        """
        Returns true if all source and target file signatures were unchanged
        from the last run and all child-tasks have successfully
        run.
        Note that each task may change the file signatures
        of its targets, as such, it cannot be assumed
        that a task may still need to run even though at some
        point this function returned True, since other tasks may
        change the sources of this task and thus its signatures may
        change.
        """
        # check if all children have run
        for t in self.targets:
            if t.has_changed(ns=self._ns):
                return False
        # check if all sources have changed since last build
        for s in self.sources:
            if s.has_changed(ns=self._ns):
                return False
        # Task was successfully run
        self.task.success = True
        return True

    @property
    def nodes_changed(self):
        if self._frozen and self._nodes_changed is not None:
            return self._nodes_changed
        elif self._frozen:
            self._nodes_changed = self._test_nodes_changed()
            return self._nodes_changed
        return self._test_nodes_changed()

    @property
    def runnable(self):
        """
        Returns True if the task can be run (i.e. all dependencies) completed
        successfully.
        """
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

    @property
    def spawning_nodes(self):
        return [node for node in self._task.sources if isinstance(node, SpawningNode)]

    def __repr__(self):
        return repr(self.task)

    @property
    def ns(self):
        """
        Returns the namespace in which the task is run. Usually this is the
        name of the command. Signatures will be kept in this namespace.
        """
        return self._ns


class DAG(object):
    """
    Represents the direct acyclic graph of the task dependency tree.
    It is initialized from a set of tasks and allows inserting new tasks using
    the :meth:`insert()` function. Runnable tasks can be queried using
    :meth:`pop_runnable_task()`.

    :param tasks: A list of TaskContainer produced using
        the :meth:`make_containers()` function.
    :param produce: A set of nodes. The tasks added to the DAG are limited
        to the tasks required for producing the given set of nodes.
    """
    def __init__(self, tasks, produce=None):
        self._waiting_tasks = []
        self._target_map = {}
        self._runnable_tasks = []
        self._produce = produce
        self.recompute(tasks)

    def recompute(self, new_tasks):
        """
        Rebuilds the DAG, i.e. computes all dependencies between tasks.

        :param new_tasks: Adds new tasks to the DAG.
        """
        # TODO: flatten the tasks here and clear dependencies upon recompute
        tasks = list(new_tasks)
        if len(self._runnable_tasks) > 0:
            tasks.extend(self._runnable_tasks)
            self._runnable_tasks.clear()
        if len(self._waiting_tasks) > 0:
            tasks.extend(self._waiting_tasks)
            self._waiting_tasks.clear()
        self._target_map.clear()
        self.insert(tasks)
        if self._produce is not None:
            self._waiting_tasks.clear()
            limited_set = set()
            produce_ids = [p.name for p in self._produce]
            required = []
            for task in tasks:
                for t in task.task.targets:
                    if t.name in produce_ids:
                        required.append(task)
            for req in required:
                limited = self._limit_selection(req)
                limited_set.add(req)
                for x in limited:
                    limited_set.add(x)
            self._waiting_tasks = [x for x in limited_set]

    def _limit_selection(self, required_task):
        """
        Returns a list of tasks required for executing the required task.
        """
        required = []
        for dep in required_task.dependencies:
            required.append(dep)
            required.extend(self._limit_selection(dep))
        return required

    def update_runnable(self):
        """
        Updates the list of runnable tasks.
        """
        for task in self._waiting_tasks:
            task.freeze()
        self._runnable_tasks = []
        new_waiting_tasks = []
        for task in self._waiting_tasks:
            if task.runnable and task.nodes_changed:
                self._runnable_tasks.append(task)
            elif not task.runnable:
                new_waiting_tasks.append(task)
            else:
                # task is runnable but no nodes have changed
                # flag the task as run
                task.has_run = True
        self._waiting_tasks = new_waiting_tasks
        for task in self._waiting_tasks:
            task.thaw()
        for task in self._runnable_tasks:
            task.thaw()

    def pop_runnable_task(self, tasks_executing=False):
        """
        Pops a runnable task from the list of tasks and returns it.
        None is returned if there are no runnable tasks left to be processed.
        If the DAG contains a dependency cycle, a DependencyCycleError is raised.
        """
        if len(self._runnable_tasks) == 0 and len(self._waiting_tasks) == 0:
            return None  # Done
        if len(self._runnable_tasks) == 0:
            self.update_runnable()
            if len(self._runnable_tasks) == 0 and not tasks_executing and len(self._waiting_tasks) != 0:
                raise DependencyCycleError('The task graph is not a DAG: Dependency cycle found!')
        if len(self._runnable_tasks) == 0:
            return None
        task = self._runnable_tasks.pop()
        return task

    def _insert_to_target_map(self, tasks):
        for task in tasks:
            for target in task.targets:
                if target.name not in self._target_map:
                    self._target_map[target.name] = []
                self._target_map[target.name].append(task)

    def insert(self, tasks):
        """
        Inserts a new task into the DAG.
        :param tasks: A list of TaskContainer to be added to the DAG.
        """
        # n = number of tasks, m = average number of source nodes per task
        # p = average number of tasks producing a target
        # for a loosly coupled task set, the complexity is O(n)
        # create map from target => task --> O(m*n)
        tasks = list(tasks)
        self._insert_to_target_map(tasks)
        k = 0
        while k < len(tasks):
            task = tasks[k]
            for src in task.sources:
                if src.name not in self._target_map and isinstance(src, SpawningNode):
                    spawned = [TaskContainer(t, ns=task.ns) for t in src.do_spawn()]
                    self._insert_to_target_map(spawned)
                    tasks.extend(spawned)
            k += 1
        # add dependencies to every task, i.e. add all tasks producing each target --> O(m*n*p)
        for task in tasks:
            for source in task.task.sources:
                if source.name not in self._target_map:
                    continue
                deps = set(self._target_map[source.name])
                deps = deps.union(set(task.dependencies))
                task.dependencies.clear()
                task.dependencies.extend(list(deps))
        self._waiting_tasks.extend(tasks)

    def has_finished(self):
        return (len(self._runnable_tasks) == 0
                and len(self._waiting_tasks) == 0)


class Executor(object):
    """
    Abstract class which can be subclassed and handles the execution of
    a DAG.

    :param ns: The namespace in which the task set is run. See :class:`wasp.signature.Signature`
        for more information on namespaces.
    """
    def __init__(self, ns=None):
        self._ns = ns
        self._dag = None
        self._consumed_nodes = []
        self._produced_nodes = []
        self._nodes_in_production = []
        self._executed_tasks = TaskCollection()
        self._executing_tasks = []
        self._success = True

    @property
    def success(self):
        return self._success

    def setup(self, dag):
        """
        Initializes the Executor with a DAG.
        """
        self._dag = dag

    @property
    def executed_tasks(self):
        """
        Returns a list of executed TaskContainers.
        """
        return self._executed_tasks

    @property
    def executing_tasks(self):
        """
        Returns a list of currently executing TaskContainers.
        """
        return self._executing_tasks

    @property
    def produced_nodes(self):
        """
        Returns a list of nodes that have been produced by
        the executed tasks.
        """
        return self._produced_nodes

    @property
    def consumed_nodes(self):
        """
        Returns a list of nodes that have been consumed by
        the executed tasks.
        """
        return self._consumed_nodes

    def task_start(self, task):
        """
        Must be called if a task is started.
        """
        self._executing_tasks.append(task)

    def task_failed(self, task):
        """
        Must be called if a task has failed.
        """
        self._cancel()
        self._success = False
        # invalidate the target nodes, such that this task is rerun
        for t in task.task.targets:
            t.signature(ns=self._ns).invalidate()

    def task_success(self, task, start=True):
        """
        Must be called if a task has finished successfully.
        """
        assert self._dag is not None, 'Call setup() first'
        self._executing_tasks.remove(task)
        self._executed_tasks.add(task.task)
        task.has_run = True
        spawned = task.task.spawn()
        if spawned is not None:
            self._dag.insert(_flatten(spawned))
        self._consumed_nodes.extend(task.task.sources)
        self._produced_nodes.extend(task.task.targets)
        if start:
            self._start()

    def _cancel(self):
        """
        Cancels the execution of DAG. Must be implemented in subclasses.
        """
        raise NotImplementedError

    def _start(self):
        """
        Starts the exeuction of tasks. This function is called by :func:`task_success`
        and must be reimplemented by the subclass.
        """
        raise NotImplementedError

    def run(self):
        """
        Runs all tasks.
        """
        self._pre_run()
        self._execute_tasks()
        self._post_run()

    def _execute_tasks(self):
        """
        Executes all tasks. This function must block until either all tasks
        have been processed or the execution is canceled. Must be reimplemented by the subclass.
        """
        raise NotImplementedError

    def _pre_run(self):
        """
        Called before :func:`_execute_tasks:.
        """
        pass

    def _post_run(self):
        """
        Called after :func:`_execute_tasks:.
        """
        # refresh all signatures that were consumed but
        # never produced. i.e. nodes that act only
        # as sources.
        consumed = set(x.name for x in self.consumed_nodes)
        produced = set(x.name for x in self.produced_nodes)
        to_update = consumed - produced
        dict_consumed = {x.name: x for x in self.consumed_nodes}
        for k, v in dict_consumed.items():
            if k not in to_update:
                continue
            sig = v.signature(ns=self._ns)
            sig.refresh()
            ctx.produced_signatures.update(sig, ns=self._ns)
            ctx.signatures.update(sig, ns=self._ns)
        # write all target signatures that were produced
        for node in self.produced_nodes:
            # target signatures were already refreshed
            # upon target.success
            sig = node.signature(ns=self._ns)
            ctx.produced_signatures.update(sig, ns=self._ns)
            ctx.signatures.update(sig, ns=self._ns)


class ParallelExecutor(Executor):
    """
    Default executor for wasp. It parallelizes the execution of the DAG by
    using a thread pool.

    :param jobs: Number of jobs to be executed simultaneously, defaults to 1.
    :param ns: The namespace in which the task set is run. See :class:`wasp.signature.Signature`
        for more information on namespaces.
    """

    class TaskRunner(object):
        """
        Callable class for executing a task.

        :param task: The task to be executed.
        :param on_success: An :class:`wasp.util.Event` object called upon success.
        :param on_fail: A :class:`wasp.util.Event` object called upon failure.
        """
        def __init__(self, task, on_success, on_fail):
            self._on_success = on_success
            self._on_fail = on_fail
            self._task = task

        def __call__(self):
            try:
                succ = run_task(self._task)
                if not succ:
                    self._on_fail.fire(self._task)
                    return
                self._on_success.fire(self._task)
            except KeyboardInterrupt:
                log.fatal(log.format_fail('Execution Interrupted!!'))
                self._on_fail.fire(self._task)

    def __init__(self, jobs=None, ns=None):
        super().__init__(ns=ns)
        self._current_jobs = 0
        self._loop = EventLoop()
        if jobs is None:
            jobs = 2*cpu_count()
        self._jobs = jobs
        self._success_event = Event(self._loop).connect(self.task_success)
        self._failed_event = Event(self._loop).connect(self.task_failed)
        self._thread_pool = ThreadPool(self._loop, jobs)
        self._loop.on_interrupt(self._thread_pool.cancel)
        self._thread_pool.on_finished(self._loop.cancel)

    def _execute_tasks(self):
        self._thread_pool.start()
        self._start()
        if not self._loop.run():
            log.log_fail('Execution Interrupted!!')

    def _start(self):
        assert self._dag is not None, 'Call setup() first'
        while True:
            if not self._loop.running and self._loop.started:
                break
            tasks_executing = len(self._executing_tasks) != 0
            if self._dag.has_finished() and not tasks_executing:
                self._thread_pool.cancel()
                break
            # attempt to start new task
            task = self._dag.pop_runnable_task(tasks_executing=tasks_executing)
            if task is None:
                if self._dag.has_finished() and not tasks_executing:
                    self._thread_pool.cancel()
                break
            try:
                task.task.check()
            except MissingArgumentError as e:
                msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                    '{0}: {1}'.format(type(e).__name__,  str(e)))
                log.fatal(msg)
                self.task_failed(task)
                break
            self.task_start(task)
            self._thread_pool.submit(
                ParallelExecutor.TaskRunner(task, self._success_event, self._failed_event))

    def _cancel(self):
        self._thread_pool.cancel()


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
    tasks = make_containers(tasks.values(), ns=ns)
    if len(tasks) == 0:
        return TaskCollection()
    dag = DAG(tasks, produce=produce)
    if executor is None:
        executor = ParallelExecutor(ns=ns)
    assert isinstance(executor, Executor)
    executor.setup(dag)
    extensions.api.tasks_execution_started(tasks, executor, dag)
    executor.run()
    extensions.api.tasks_execution_finished(tasks, executor, dag)
    ctx.current_namespace = oldns
    return executor.executed_tasks


def run_task(task):
    """
    Runs a task and logs its result.

    :param task: A :class:`TaskContainer` to be executed.
    """
    ret = extensions.api.run_task(task)
    if ret != NotImplemented:
        return ret
    extensions.api.task_started(task)
    real_task = task.task
    for target in task.targets:
        target.before_run(target=True)
    for source in task.sources:
        source.before_run(target=False)
    try:
        real_task.prepare()
        real_task.run()
        if real_task.success:
            real_task.on_success()
        else:
            real_task.on_fail()
            log.debug(log.format_fail('Task `{}` failed'.format(type(real_task).__name__)))
        real_task.postprocess()
    except TaskFailedError as e:
        real_task.success = False
        log.fatal(str(e))
    except Exception as e:
        msg = log.format_fail(''.join(traceback.format_tb(e.__traceback__)),
                '{0}: {1}'.format(type(e).__name__,  str(e)))
        log.fatal(msg)
        real_task.success = False
    if real_task.success:
        for node in real_task.targets:
            node.signature(task.ns).refresh()
    for target in task.targets:
        target.after_run(target=True)
    for source in task.sources:
        source.after_run(target=False)
    extensions.api.task_finished(task)
    return task.task.success


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
    Flattens a list of task and creates :class:`TaskContainer` objects.

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
            task = TaskContainer(task, ns=ns)
            new_sources = _uniquify(task.sources)
            task.sources.clear()
            task.sources.extend(new_sources)
            new_targets = _uniquify(task.targets)
            task.targets.clear()
            task.targets.extend(new_targets)
            ret.append(task)
    return ret


def make_containers(tasks, ns=None):
    """
    Flattens the list of :class:`wasp.Task` in tasks
    and returns a list of :class:`TaskContainer`.
    """
    return _flatten(tasks, ns=ns)
