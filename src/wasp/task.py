from .node import nodes, is_symbolic_node_string, SymbolicNode, node, Node
from uuid import uuid4 as uuid
from .util import CallableList, is_iterable
from .argument import Argument, ArgumentCollection
from .commands import Command
from . import log, decorators

from functools import reduce
from itertools import chain as iter_chain
import operator


class MissingArgumentError(Exception):
    pass


class Task(object):
    def __init__(self, sources=None, targets=None, children=None, always=False, fun=None):
        self._sources = nodes(sources)
        self._targets = nodes(targets)
        if len(self._sources) == 0 and len(self._targets) == 0:
            always = True
        if children is None:
            children = []
        assert is_iterable(children)
        if not isinstance(children, list):
            children = list(children)
        self.children = children
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
        self._logger = log.clone()
        self._result = ArgumentCollection()
        self._used_nodes = []
        self._required_arguments = []

    def _make_id(self):
        return str(uuid())

    @property
    def log(self):
        return self._logger

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

    def check(self):
        """
        Called before task execution (also before prepare). This function
        retrieves all information from dependency nodes and checks if all required arguments
        were given. If not, it is attempted to retrieve the required information using :ref:Argument.retrieve_all().
        This function is called in the main thread and may access the wasp-context.
        If this fails as well, a :ref:MissingArgumentError is thrown.
        """
        for node in self._used_nodes:
            # retrieve all nodes
            if isinstance(node, SymbolicNode):
                for arg in node.read().values():
                    if arg.key not in self.arguments or self.arguments[arg.key].is_empty:
                        self.use(arg)
        for arg in self._required_arguments:
            if arg.key not in self.arguments:
                # attempt to retrieve the argument from the common sources
                arg = Argument(arg.key).retrieve_all()
                if arg.is_empty:
                    raise MissingArgumentError('Missing argument for task:'
                                               ' Required argument "{1}" is empty.'.format(self.key, arg.key))
                self.arguments.add(arg)
            elif self.arguments[arg.key].is_empty:
                self.arguments[arg.key].retrieve_all()
                if self.arguments[arg.key].is_empty():
                    raise MissingArgumentError('Missing argument for task:'
                                               ' Required argument "{1}" is empty.'.format(self.key, arg.key))

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
            elif isinstance(a, list):
                self.use(*a)
        for k, a in kw.items():
            if not isinstance(a, str):
                a = str(a)
            self.use_arg(Argument(k).assign(a))
        return self

    def use_arg(self, arg):
        for c in self.children:
            c.use_arg(arg)
        self.arguments.add(arg)

    def get_result(self):
        return self._result

    def set_result(self, result):
        self._result = result

    result = property(get_result, set_result)

    def require(self, *arguments):
        for arg in arguments:
            # add arguments to a list and check them before execution
            if arg is None:
                continue
            if isinstance(arg, str):
                ext = [Argument(arg)]
            elif isinstance(arg, list):
                ext = [Argument(x) if isinstance(x, str) else x for x in arg]
            else:
                assert False, 'Unrecognized type in Task.require() arguments. Accepted are str or list thereof.'
            self._required_arguments.extend(ext)
        return self


class TaskGroup(Task):
    def __init__(self, children):
        assert is_iterable(children), 'chilren argument to TaskGroup() is expected to be iterable.'
        # this should all be O(n+m) assuming n is the total number of sources
        # and m is the total number of targets
        # flatten sources and targets first
        sources = self._flatten(children, lambda x: x.sources)
        s_all = list(sources)
        targets = self._flatten(children, lambda x: x.targets)
        t_all = list(targets)
        targets_new = []
        for t in targets.values():
            # remove source node if it is also a target
            # otherwise, the target node in question is external
            # and the source node is external as well.
            if t.key in sources:
                del sources[t.key]
            else:
                targets_new.append(t)
        self._grouped_sources = s_all
        self._grouped_targets = t_all
        super().__init__(sources=list(sources.values()), targets=targets_new, children=children, always=True)

    @property
    def grouped_targets(self):
        raise NotImplementedError  # TODO: wrong!
        return self._grouped_targets

    @property
    def grouped_sources(self):
        raise NotImplementedError  # TODO: wrong!
        return self._grouped_sources

    def _flatten(self, tasks, fun):
        # base case if called with one task
        if isinstance(tasks, Task):
            return {x.key: x for x in fun(tasks)}
        # get all task items
        lst = list(iter_chain(*[fun(task) for task in tasks]))
        # create a dict from them
        ret = dict(zip([x.key for x in lst], lst))
        for task in tasks:
            for c in task.children:
                ret.update(self._flatten(c, fun))
        # recursively flatten all children... haskell style :P
        # ret.update(dict(chain([self._flatten(c, fun).items() for task in tasks for c in task.children])))
        return ret

    def use(self, *args, **kw):
        super().use(*args, **kw)
        for child in self.children:
            child.use(*args, **kw)
        return self

    def __repr__(self):
        return '[' + ', '.join([repr(c) for c in self.children]) + ']'

    def __iadd__(self, other):
        self.children.append(other)
        sources = self._flatten(other, lambda x: x.sources)
        targets = self._flatten(other, lambda x: x.targets)
        for s in sources:
            for t in self.targets:
                if t.key == s:
                    self.targets.remove(t)
        for t in targets:
            for s in self.sources:
                if t == s.key:
                    self.sources.remove(s)
        self.targets.extend(targets.values())
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
        assert isinstance(arg, Task), '*args must be a list of Tasks, but was: {0}'.format(type(arg).__name__)
    if len(args) == 1 and collapse:
        return args[0]
    return TaskGroup(args)


class ChainingTaskGroup(TaskGroup):

    def __init__(self, children):
        super().__init__(children)
        # create dependencies between the tasks
        previous = None
        for a in children:
            if previous is None:
                previous = a
                continue
            a.use(previous)
            previous = a

    def __iadd__(self, other):
        if len(self.children) > 0:
            other.use(self.children[-1])
        return super().__iadd__(other)


def chain(*args):
    return ChainingTaskGroup(args)


def fail():
    t = Task(always=True)

    def _fail():
        t.success = False
    t.run.append(_fail)
    return task


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