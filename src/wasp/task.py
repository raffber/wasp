from .node import nodes, is_symbolic_node_string, SymbolicNode, node, Node
from .util import CallableList, is_iterable
from .argument import Argument, ArgumentCollection
from .commands import Command
from . import decorators

from functools import reduce
import operator


class MissingArgumentError(Exception):
    pass


class TaskFailedError(Exception):
    pass


class Task(object):
    """
    ``Tasks`` are the central unit of execution of ``wasp``. A build process is formulated as
    as a set of ``Tasks``, which consume ``Nodes`` (source nodes) and produce
    ``Nodes`` (target nodes). Source nodes may either be specified in the constructor,
    with the :func:`Task.use` or the :func:`Task.depends` function.
    Target nodes are specified in the constructor or with the :func:`Task.produce` function.
    Furthermore, information is passed to a task using  :class:`wasp.argument.Argument` objects,
    which are key-value pairs. They may also be passed to the :class:`Task` using the :func:`Task.use`
    function or using :class:`wasp.node.SymbolicNode` objects.

    It is distinguished between **creation** and **execution** time of tasks. First, during
    creation time, a set of tasks and the relation between the tasks is defined. Second,
    during execution time, a directed-acyclic graph (DAG) is constructed, the executable tasks
    are determined and executed until all tasks are finished (or a task has failed).

    During execution time, the following functions are called in order:

        #. :func:`Task.check`: Should retrieve all arguments the task requires and throw a MissingArgumentError()
            in case an argument is not present. Additionaly, it may spawn tasks which are inserted into
            the DAG to retrieve the missing arguments. A task may only spawn tasks once. This function
            may be executed multiple times in the main thread.
        #. :func:`Task.prepare`: May be used to prepare the task for execution.
        #. :func:`Task.run`: This function should actually run the task and set ``task.success``.
        #. :func:`Task.on_fail` or :func:`Task.on_success`: Called depending on whether task execution was successful.
        #. :func:`Task.postprocess`: Allows the task to do some postprocessing.
        #. :func:`Task.spawn`: May return new tasks which are added to the DAG. :func:`Task.spawn`
            is called even if the task is not run (since it was determined that all source and
            target nodes are still up-to-date)

    Arguments may be passed to a task during creation time or they can be passed using
    SymbolicNodes during execution time. It is important to note, that whether a task
    is executed only depends on the signatures of its source and target nodes and not on
    the arguments passed to it during creation time. Thus, if an argument can change
    between differnt runs of ``wasp``, the argument must be passed using a node. For example::

      t = Task(fun=foo).use(':config')
      node(':config').write(key=value)

    Note, that the order of the above statements is not relevant, since the ':config' node is
    only read at execution time.

    By default, tasks are executed in parallel by separate threads using
    :class:`wasp.execution.ParallelExecutor`.

    Several methods (such as ``run()``) are implemented using :class:`wasp.util.CallableList`
    objects. Thus, they allow adding multiple functions to be called, by default, only
    ``task._run`` is called. For example::

    task = Task()
    custom_run = lambda task: task.log.info('Hello, World!')
    task.run.append(custom_run)

    If ``task.run()`` is called, the additional function ``custom_run`` is called as well (after
    ``task._run()`` was called).

    :param sources: Defines the source nodes of this task. See :func:`wasp.node.nodes` for
        all allowed types.
    :param targets: Defines the target nodes of this task. See :func:`wasp.node.nodes` for
        all allowed types.
    :param always: Determines whether the task should always be executed regardless of the
        state of its source and target node.
    :param fun: A callable which (if not None) is added to ``task.run``.
    """
    def __init__(self, sources=None, targets=None, always=False, fun=None):
        self._sources = nodes(sources)
        self._targets = nodes(targets)
        self._has_run = False
        self._always = always
        self._success = False
        self._arguments = ArgumentCollection()
        self._run_list = CallableList(arg=self)
        self._run_list.append(lambda x: self._run())
        if fun is not None:
            self._run_list.append(fun)
        self._prepare_list = CallableList(arg=self)
        self._prepare_list.append(lambda x: self._prepare())
        self._success_list = CallableList(arg=self)
        self._success_list.append(lambda x: self._on_success())
        self._fail_list = CallableList(arg=self)
        self._fail_list.append(lambda x: self._on_fail())
        self._postprocess_list = CallableList(arg=self)
        self._postprocess_list.append(lambda x: self._postprocess())
        self._spawn_list = CallableList(arg=self).collect(lambda ret: reduce(operator.add, ret))
        self._spawn_list.append(lambda x: self._spawn())
        self._logger = None
        self._result = ArgumentCollection()
        self._used_nodes = []
        self._required_arguments = []
        self._init()
        self._noop = False

    def get_noop(self):
        return self._noop

    def set_noop(self, noop):
        self._noop = noop

    noop = property(get_noop, set_noop)
    """
    Provides a preformance hint to the executor, specifying that the task is actually
    to a very simple operation. Note that the task is still executed using the
    default sequence of method calls.
    """

    def _init(self):
        """
        May be overwritten for initializing the task.
        """
        pass

    def get_log(self):
        return self._logger

    def set_log(self, logger):
        self._logger = logger

    log = property(get_log, set_log)
    """
    Gets or sets the :class:`wasp.logging.Logger` object the task should
    use for output.
    """

    def get_always(self):
        return self._always

    def set_always(self, value):
        self._always = value

    always = property(get_always, set_always)
    """
    Defines whether the task should be run regardless of the states of
    the source and target nodes.
    """

    @property
    def sources(self):
        """
        Returns a list of all source nodes of the task.
        """
        return self._sources

    @property
    def targets(self):
        """
        Returns a list of all target nodes of the task.
        """
        return self._targets

    def check(self):
        """
        Retrieves the required arguments of the task by reading all source nodes.
        The function throws a ``MissingArgumentError`` in case a required arguments
        was not found. Required arguments may be configured by calling ``task.require()``.
        """
        for node in self._used_nodes:
            # retrieve all nodes
            if isinstance(node, SymbolicNode):
                self.use(node.read())
        for argkey in self._required_arguments:
            if argkey not in self.arguments or self.arguments[argkey].is_empty:
                # NOTE: Think about this feature some more:
                # I feel this leads to somewhat unpredictable behaviour,
                # since some arguments are `magically` injected.
                # it's better to have this more explicit.
                # attempt to retrieve the argument from the common sources
                # arg = Argument(argkey).retrieve_all()
                # if arg.is_empty:
                raise MissingArgumentError('Missing argument for task: '
                                               'Required argument `{}` is empty.'.format(argkey))

    @property
    def prepare(self):
        """
        Returns a :class:`wasp.util.CallableList`. ``prepare()`` is called before
        ``run()``.
        """
        return self._prepare_list

    def _prepare(self):
        pass

    @property
    def on_success(self):
        """
        Returns a :class:`wasp.util.CallableList`. ``on_success()`` is called in
        case the target succeeded.
        """
        return self._success_list

    def _on_success(self):
        for node in self.targets:
            if isinstance(node, SymbolicNode):
                node.write(self.result)

    @property
    def on_fail(self):
        """
        Returns a :class:`wasp.util.CallableList`. ``on_fail()`` is called in
        case the target failed.
        """
        return self._fail_list

    def _on_fail(self):
        pass

    @property
    def postprocess(self):
        """
        Returns a :class:`wasp.util.CallableList`. ``postprocess()`` is called
        after ``run()``.
        """
        return self._postprocess_list

    def _postprocess(self):
        pass

    @property
    def spawn(self):
        """
        Returns new tasks that should be added to the execution.
        spawn() is called after run() and is called even if run()
        was not called because it was determined that running the
        task was not necessary.

        :return: Returns a list of tasks to be added to the execution.
        """
        return self._spawn_list

    def _spawn(self):
        pass

    @property
    def run(self):
        """
        Returns a :class:`wasp.util.CallableList`. This function
        should actually run the task.
        """
        return self._run_list

    def _run(self):
        self.result.update(self.arguments)
        self.success = True

    def touched(self):
        """
        Allows the execution engine to optimize the execution of this
        task, by only refreshing the signatures of the targets that
        were actually modified by this task.

        :return: All targets that have been modified. The default
            implementation returns all targets.
        """
        return self._targets

    @property
    def new_nodes(self):
        return None

    def produce(self, *args):
        """
        Adds target nodes to the task.
        The function accepts the same positional arguments as :func:`wasp.node.nodes`.
        """
        ext = nodes(args)
        self.targets.extend(ext)
        return self

    def depends(self, *args, use=True):
        """
        Adds source nodes to the task.
        The function accepts the same positional arguments as :func:`wasp.node.nodes`.

        :param use: Defines whether the source nodes should also be used for retrieving
            arguments (i.e. by calling ``task.use()``)
        """
        ext = nodes(args)
        self.sources.extend(ext)
        if not use:
            return
        for node in ext:
            if isinstance(node, SymbolicNode):
                self.use(node)
        return self

    def set_has_run(self, has_run):
        self._has_run = has_run

    def get_has_run(self):
        return self._has_run

    has_run = property(get_has_run, set_has_run)
    """
    This property is set by the execution engine and returns whether the
    task was actually run.
    """

    def set_success(self, suc):
        self._success = suc

    def get_success(self):
        return self._success

    success = property(get_success, set_success)
    """
    Gets or sets whether the task has run successfully. If the task
    was not run, this property is set to True.
    """

    @property
    def arguments(self):
        """
        Returns the :class:`wasp.argument.ArgumentCollection` object for
        this task.
        """
        return self._arguments

    def use(self, *args, **kw):
        """
        This function is used to pass information to a task, to define
        information sources or dependencies between tasks. It accepts an
        argument tuple of the following types:

         * :class:`wasp.argument.Argument`
         * :class:`wasp.argument.ArgumentCollection`: uses all its arguments
         * :class:`wasp.node.SymbolicNode`: Adds the node as a dependency and retrieves
            arguments from it.
         * :class:`wasp.node.Node`: Adds the node as a dependency.
         * :class:`Task`: Adds the task as a dependency of ``self`` by creating an empty node.
         * ``str``: If formatted as a valid identifier for a :class:`wasp.node.SymbolicNode`
            uses the node. Otherwise, an empty argument is added and it is attempted to
            fill it automatically (by calling ``Argument.retrieve_all()``).
         * :class:`TaskGroup`: Uses the ``group.target_task`` if given,
            otherwise all tasks contained in the task group
         * Also accepts an iterable objects of the above types.

        :param *args: Tuple of object with the above types.
        :param **kw: key-value pairs to be used as arguments.
        """
        for a in args:
            if isinstance(a, Argument):
                self.use_arg(a)
            elif isinstance(a, ArgumentCollection):
                for x in a.values():
                    self.use_arg(x)
            elif isinstance(a, TaskGroup):
                if a.target_task is None:
                    for t in a.tasks:
                        self.use(t)
                else:
                    self.use(a.target_task)
            elif isinstance(a, SymbolicNode):
                self._used_nodes.append(a)
                self.sources.append(a)
            elif isinstance(a, Node):
                self.sources.append(a)
            elif isinstance(a, Task):
                x = SymbolicNode(discard=True)
                a.produce(x)
                self._used_nodes.append(x)
                self.sources.append(x)
            elif isinstance(a, str):
                if is_symbolic_node_string(a):
                    x = node(a)
                    self._used_nodes.append(x)
                    self.sources.append(x)
                else:
                    arg = Argument(a).retrieve_all()
                    self.use_arg(arg)
            elif is_iterable(a):
                self.use(*a)
        for k, a in kw.items():
            self.use_arg(Argument(k).assign(a))
        return self

    def use_arg(self, arg):
        """
        Adds an argument to ``self.arguments``.
        """
        self.arguments.add(arg)

    def use_catenate(self, arg):
        """
        When an argument is used multiple times, this function creates a list of
        the values of each argument in ``self.arguments``. This is useful for
        injecting flags or multiple arguments into one key. (e.g. 'CFLAGS')
        """
        if arg.name not in self.arguments:
            item = Argument(arg.name, value=[])
            self.arguments.add(item)
        else:
            item = self.arguments[arg.name]
        if is_iterable(arg.value):
            item.value.extend(list(arg.value))
        else:
            item.value.append(arg.value)

    def get_result(self):
        return self._result

    def set_result(self, result):
        self._result = result

    result = property(get_result, set_result)
    """
    Returns the result of the task. Expected to be of type ``wasp.argument.ArgumentCollection`.
    This collection is then written to all target :class:`wasp.node.SymbolicNode` objects, s.t.
    information can be passed between different tasks.
    """

    def require(self, *arguments):
        """
        Defines that a certain argument is required for the execution of a task.
        This function accepts the following arguments:

         * ``str``: Used as argument key.
         * An iterable of the above types.
        """
        for arg in arguments:
            if arg is None:
                continue
            if isinstance(arg, str):
                argkey = arg
            elif is_iterable(arg):
                self.require(*arg)
                continue
            else:
                assert False, 'Unrecognized type in Task.require() arguments. Accepted are str or list thereof.'
            self._required_arguments.append(argkey)
        return self


def empty():
    """
    Returns an empty task which does nothing.
    """
    t = Task(always=True)
    return t


class CollectTask(Task):

    def __init__(self, sources=None, targets=None, merge=True):
        super().__init__(sources=sources, targets=targets, always=True)
        self._merge = merge

    def _merge_arg(self, arg):
        if arg.key not in self.result or not self._merge:
            self.result.add(arg)
            return
        v = arg.value
        curarg = self.result[arg.key]
        if not isinstance(v, list):
            v = [v]
        if not isinstance(curarg.value, list):
            curarg.value = [curarg.value]
        curarg.value.extend(v)

    def run(self):
        for node in self.sources:
            if isinstance(node, SymbolicNode):
                for arg in node.read().values():
                    self._merge_arg(arg)
        for arg in self.arguments:
            self._merge_arg(arg)
        self.success = True


def collect(*args, merge=True):
    node_args = nodes(args)
    t = CollectTask(sources=node_args, merge=merge)
    return t


class TaskGroup(object):
    """
    A group of :class:`Task` objects.

    :param tasks: iterable of :class:`Task` objects to be grouped.
    :param target_task: Task which acts as a target for ``produce()`` and ``use()`` for
        other tasks.
    """
    def __init__(self, tasks, target_task=None):
        assert is_iterable(tasks), 'tasks argument to TaskGroup() is expected to be iterable.'
        self._tasks = list(tasks)
        self._target_task = None

    @property
    def target_task(self):
        return self._target_task

    @property
    def tasks(self):
        """
        Returns a list of tasks grouped by this object.
        """
        return self._tasks

    @property
    def targets(self):
        """
        Returns a ``set`` of all targets of the grouped tasks.
        """
        ts = []
        for t in self._tasks:
            ts.extend(t.targets)
        return set(ts)

    @property
    def sources(self):
        """
        Returns a ``set`` of all sources of the grouped tasks.
        """
        ts = []
        for t in self._tasks:
            ts.extend(t.sources)
        return set(ts)

    def produce(self, *args):
        """
        Adds a node which is updated, once all tasks of this group have
        finished.

        :return: self
        """
        def _fun(t):
            t.result = t.arguments
            t.success = True
        if self._target_task is None:
            self._target_task = Task(fun=_fun)
            self._tasks.append(self._target_task)
        for t in self._tasks:
            if self._target_task is not t:
                self._target_task.use(t)
        self._target_task.produce(*args)
        return self

    def append(self, task):
        """
        Appends a :class:`Task` or :class:`TaskGroup` to this
        object.
        """
        if isinstance(task, Task):
            self._tasks.append(task)
            return
        assert isinstance(task, TaskGroup), 'Expected a Task or a TaskGroup' \
                ', got `{0}`'.format(task.__class__.__name__)
        for t in task.tasks:
            self.append(t)

    def use(self, *args, **kw):
        """
        Calls ``task.use`` for every task in ``self``.
        Accepts the same arguments as :func:`Task.use`.

        :return: self
        """
        for task in self._tasks:
            task.use(*args, **kw)
        return self

    def __iadd__(self, other):
        self.append(other)
        return self


def _flatten(args):
    if not is_iterable(args):
        return [args]
    ret = []
    for arg in args:
        if is_iterable(arg):
            ret += _flatten(arg)
        else:
            ret.append(arg)
    return ret


def group(*args, collapse=True, target_task=None):
    """
    Returns a :class:`TaskGroup` object based on the arguments.
    """
    args = _flatten(args)
    for arg in args:
        assert isinstance(arg, Task) or isinstance(arg, TaskGroup), \
            '*args must be a tuple of Tasks, but was: {0}'.format(type(arg).__name__)
    if len(args) == 1 and collapse:
        return args[0]
    return TaskGroup(args, target_task=target_task)


class ChainingTaskGroup(TaskGroup):
    """
    Group of tasks executed after each other.
    """

    def __init__(self, tasks):
        super().__init__(tasks)
        # create dependencies between the tasks
        previous = None
        for a in tasks:
            if previous is None:
                previous = a
                continue
            a.use(previous)
            previous = a

    def append(self, task):
        if isinstance(task, Task):
            if len(self.tasks) > 0:
                task.use(self.tasks[-1])
            self._tasks.append(task)
            return
        assert isinstance(task, TaskGroup), 'Expected a Task or a TaskGroup' \
                ', got `{0}`'.format(task.__class__.__name__)
        for t in task.tasks:
            self.append(t)


def chain(*args):
    """
    Creates a :class:`ChainingTaskGroup` object using the arguments.
    """
    return ChainingTaskGroup(args)


class task(object):
    """
    Decorator for registring a function as a task.

    :param command: The command for which the task is created.
    :param sources: List of nodes as sources.
    :param targets: List of nodes as targets.
    :param always: Defines whether the task should be executed regardless of the state
        of its source and target nodes.
    :param description: Description of the task to be printed to the user.
    :param command_depends: List of command names, which are executed before the command
        for which this task is registered.
    """
    def __init__(self, command, sources=None, targets=None, always=False, description=None, command_depends=None):
        self._command = command
        self._sources = sources
        self._targets = targets
        self._always = always
        self._description = description
        self._command_depends = command_depends

    def __call__(self, f):
        def command_fun():
            t = Task(sources=self._sources, targets=self._targets, always=self._always, fun=f)
            return t
        com = Command(self._command, command_fun, description=self._description, depends=self._command_depends)
        decorators.commands.append(com)
        return f


class TaskCollection(dict):
    """
    dict-like object to store tasks.
    """

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
        if isinstance(task, TaskGroup):
            for t in task.tasks:
                self.add(t)
            return
        if is_iterable(task):
            for t in task:
                self.add(t)
            return
        assert isinstance(task, Task)
        self[id(task)] = task
