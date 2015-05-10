from .node import nodes, is_symbolic_node_string, SymbolicNode, node, Node
from uuid import uuid4 as uuid
from .util import CallableList, is_iterable
from .argument import Argument, ArgumentCollection
from .commands import Command
from . import decorators

from functools import reduce
import operator


class MissingArgumentError(Exception):
    pass


class Task(object):
    """
    ``Tasks`` are the central unit of execution of ``wasp``. A build process is formulated as
    as a set of ``Tasks``, which consume ``Nodes`` (i.e. depend on, source nodes) and produce
    ``Nodes`` (target nodes).

    TODO: more
    """
    def __init__(self, sources=None, targets=None, always=False, fun=None, noop=False):
        self._sources = nodes(sources)
        self._targets = nodes(targets)
        if len(self._sources) == 0 and len(self._targets) == 0:
            always = True
        self._has_run = False
        self._always = always
        self._success = False
        self._arguments = ArgumentCollection()
        self._key = self._make_id()
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
        assert isinstance(noop, bool)
        self._noop = noop

    @property
    def noop(self):
        return self._noop

    def _init(self):
        pass

    def _make_id(self):
        return str(uuid())

    def get_log(self):
        return self._logger

    def set_log(self, logger):
        self._logger = logger

    log = property(get_log, set_log)

    def get_always(self):
        return self._always

    def set_always(self, value):
        self._always = value

    always = property(get_always, set_always)

    @property
    def sources(self):
        return self._sources

    def __eq__(self, other):
        return other.identfier == self._key

    def __ne__(self, other):
        return not (other.identfier == self._key)

    def check(self, spawn=True):
        for node in self._used_nodes:
            # retrieve all nodes
            if isinstance(node, SymbolicNode):
                self.use(node.read())
        ret = []
        for argkey, spawner in self._required_arguments:
            if argkey not in self.arguments or self.arguments[argkey].is_empty:
                # NOTE: Think about this feature some more:
                # I feel this leads to somewhat unpredictable behaviour,
                # since some arguments are `magically` injected.
                # it's better to have this more explicit.
                # attempt to retrieve the argument from the common sources
                # arg = Argument(argkey).retrieve_all()
                # if arg.is_empty:
                if spawner is None or not spawn:
                    raise MissingArgumentError(
                        'Missing argument for task: Required argument "{1}" is empty.'
                        .format(self.key, argkey))
                t = spawner()
                self.use(t)
                ret.append(t)
        if not len(ret) == 0:
            return ret
        return None

    @property
    def prepare(self):
        return self._prepare_list

    def _prepare(self):
        pass

    @property
    def on_success(self):
        return self._success_list

    def _on_success(self):
        for node in self.targets:
            if isinstance(node, SymbolicNode):
                node.write(self.result)

    @property
    def on_fail(self):
        return self._fail_list

    def _on_fail(self):
        pass

    @property
    def postprocess(self):
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
        return self._run_list

    def _run(self):
        self.success = True

    def touched(self):
        return self._targets

    @property
    def targets(self):
        return self._targets

    def produce(self, *args):
        """
        Adds targets to the task.
        The function accepts the same positional arguments as :ref:make_nodes().
        """
        ext = nodes(args)
        self.targets.extend(ext)
        return self

    def depends(self, *args, use=True):
        """
        Sets dependencies to the task.
        The function accepts the same positional arguments as :ref:make_nodes().
        """
        ext = nodes(args)
        self.sources.extend(ext)
        if not use:
            return
        for node in ext:
            if isinstance(node, SymbolicNode):
                self.use(node.read())
        return self

    def set_has_run(self, has_run):
        self._has_run = has_run

    def get_has_run(self):
        return self._has_run

    has_run = property(get_has_run, set_has_run)

    @property
    def key(self):
        return self._key

    def set_success(self, suc):
        self._success = suc

    def get_success(self):
        return self._success

    success = property(get_success, set_success)

    @property
    def arguments(self):
        return self._arguments

    def use(self, *args, **kw):
        for a in args:
            if isinstance(a, Argument):
                self.use_arg(a)
            elif isinstance(a, ArgumentCollection):
                for x in a.values():
                    self.use_arg(x)
            elif isinstance(a, TaskGroup):
                for t in a.tasks:
                    self.use(t)
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
        self.arguments.add(arg)

    def get_result(self):
        return self._result

    def set_result(self, result):
        self._result = result

    result = property(get_result, set_result)

    def require(self, *arguments, spawn=None):
        for arg in arguments:
            spawner = spawn
            # add arguments to a list and check them before execution
            if arg is None:
                continue
            if isinstance(arg, str):
                argkey = arg
            elif isinstance(arg, list):
                self.require(*arg)
                continue
            elif isinstance(arg, tuple):
                argkey, spawner = arg
                assert isinstance(argkey, str), 'Task.require() expects a tuple of (str, callable).'
                assert callable(spawner), 'Task.require() expects a tuple of (str, callable).'
            else:
                assert False, 'Unrecognized type in Task.require() arguments. Accepted are str or list thereof.'
            self._required_arguments.append((argkey, spawner))
        return self


class TaskGroup(object):
    def __init__(self, tasks):
        assert is_iterable(tasks), 'tasks argument to TaskGroup() is expected to be iterable.'
        self._tasks = list(tasks)

    @property
    def tasks(self):
        return self._tasks

    def produce(self, *args):
        def _fun(t):
            t.result = t.arguments
            t.success = True
        empty = Task(noop=True, fun=_fun)
        for t in self._tasks:
            empty.use(t)
        empty.produce(*args)
        self._tasks.append(empty)
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


def group(*args, collapse=True):
    args = _flatten(args)
    for arg in args:
        assert isinstance(arg, Task) or isinstance(arg, TaskGroup), '*args must be a list of Tasks, but was: {0}'.format(type(arg).__name__)
    if len(args) == 1 and collapse:
        return args[0]
    return TaskGroup(args)


class ChainingTaskGroup(TaskGroup):

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

    def __iadd__(self, other):
        if len(self.tasks) > 0:
            other.use(self.tasks[-1])
        return self


def chain(*args):
    return ChainingTaskGroup(args)


class task(object):
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
        assert isinstance(task, Task)
        self[task.key] = task
