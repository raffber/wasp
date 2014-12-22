from .node import make_nodes, is_symbolic_node_string, SymbolicNode, make_node
from uuid import uuid4 as uuid
from .util import CallableList, is_iterable
from .argument import Argument, ArgumentCollection
from .logging import Logger

from functools import reduce
from itertools import chain
import operator


class MissingArgumentError(Exception):
    pass


class Task(object):
    def __init__(self, sources=[], targets=[], children=[], always=False, identifier=None, fun=None):
        self._sources = make_nodes(sources)
        self._targets = make_nodes(targets)
        if len(self._sources) == 0 and len(self._targets) == 0:
            always = True
        assert isinstance(children, list)
        self.children = children
        self._has_run = False
        self._always = always
        self._success = False
        self._arguments = ArgumentCollection()
        if identifier is None:
            self._id = self._make_id()
        else:
            self._id = identifier
        self._run_list = CallableList()
        self._run_list.append(self._run)
        if fun is not None:
            self._run_list.append(fun)
        self._prepare_list = CallableList()
        self._prepare_list.append(self._prepare)
        self._success_list = CallableList()
        self._success_list.append(self._on_success)
        self._fail_list = CallableList()
        self._fail_list.append(self._on_fail)
        self._postprocess_list = CallableList()
        self._postprocess_list.append(self._postprocess)
        self._spawn_list = CallableList().collect(lambda ret: reduce(operator.add, ret))
        self._spawn_list.append(self._spawn)
        self._logger = Logger()
        self._result = ArgumentCollection()
        self._used_nodes = []
        self._required_arguments = []

    def _make_id(self):
        return str(uuid())

    @property
    def log(self):
        return self._logger

    @property
    def always(self):
        return self._always

    @property
    def sources(self):
        return self._sources

    def __eq__(self, other):
        return other.identfier == self._id

    def __ne__(self, other):
        return not (other.identfier == self._id)

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
            self.use(node.read())
        for arg in self._required_arguments:
            if arg.key not in self.arguments:
                # attempt to retrieve the argument from the common sources
                arg = Argument(arg.key).retrieve_all()
                if arg.is_empty:
                    raise MissingArgumentError('Missing argument for task "{0}":'
                                               ' Required argument "{1}" is empty.'.format(self.identifier, arg.key))
                self.arguments.add(arg)
            elif self.arguments[arg.key].is_empty:
                self.arguments[arg.key].retrieve_all()
                if self.arguments[arg.key].is_empty():
                    raise MissingArgumentError('Missing argument for task "{0}":'
                                               ' Required argument "{1}" is empty.'.format(self.identifier, arg.key))

    @property
    def prepare(self):
        return self._prepare_list

    def _prepare(self):
        pass

    @property
    def on_success(self):
        return self._success_list

    def _on_success(self):
        pass

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
        TODO: check documentation
        """
        nodes = make_nodes(args)
        self.targets.extend(nodes)
        return self

    def depends(self, *args, use=True):
        """
        Sets dependencies to the task.
        The function accepts the same positional arguments as :ref:make_nodes().
        TODO: check documentation
        """
        nodes = make_nodes(args)
        self.sources.extend(nodes)
        if not use:
            return
        for node in nodes:
            if isinstance(node, SymbolicNode):
                self.use(node.read())
        return self

    def set_has_run(self, has_run):
        self._has_run = has_run

    def get_has_run(self):
        # returns true if all source and target file signatures were unchanged
        # from the last run and all child-tasks have successfully
        # run.
        # note that each task may change the file signatures
        # of its targets, as such, it cannot be assumed
        # that a task may still need to run even though at some
        # point this function returned True, since other tasks may
        # change the sources of this task and thus its signatures may
        # change.
        if self.always:
            return False
        if self._has_run:
            return True
        # check if all children have run
        for task in self.children:
            if not task.has_run:
                return False
        for t in self.targets:
            if t.has_changed():
                return False
        # check if all sources have changed since last build
        for s in self.sources:
            if s.has_changed():
                return False
        # Task was successfully run
        self.success = True
        return True

    has_run = property(get_has_run, set_has_run)

    @property
    def identifier(self):
        return self._id

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
                self.arguments.update(a)
            elif isinstance(a, SymbolicNode):
                self.use_node(a)
            elif isinstance(a, str):
                if is_symbolic_node_string(a):
                    self.use_node(a)
                else:
                    arg = Argument(a).retrieve_all()
                    self.use_arg(arg)
            elif isinstance(a, list):
                self.use(*a)
        for k, a in kw.items():
            self.use_arg(Argument(k).assign(a))
        return self

    def use_node(self, node):
        node = make_node(node)
        assert isinstance(node, SymbolicNode), 'Only subclasses of SymbolicNode can be used by a task'
        self._used_nodes.append(node)

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
            self._required_arguments.extend(ext)
        return self


class TaskGroup(Task):
    def __init__(self, children):
        # this should all be O(n+m) assuming n is the total number of sources
        # and m is the total number of targets
        # flatten sources and targets first
        sources = self._flatten(children, lambda x: x.sources)
        targets = self._flatten(children, lambda x: x.targets)
        targets_new = []
        for t in targets.values():
            # remove source node if it is also a target
            # otherwise, the target node in question is external
            # and the source node is external as well.
            if t.identifier in sources:
                del sources[t.identifier]
            else:
                targets_new.append(t)
        super().__init__(sources=list(sources.values()), targets=targets_new, children=children, always=True)

    def _flatten(self, tasks, fun):
        # get all task items
        lst = chain(*[fun(task) for task in tasks])
        # create a dict from them
        ret = dict(zip([x.identifier for x in lst], lst))
        # recursively flatten all children... haskell style :P
        ret.update(dict(chain([self._flatten(c, fun).items() for task in tasks for c in task.children])))
        return ret

    def use(self, *args, **kw):
        for child in self.children:
            child.use(*args, **kw)
        return self

    def __repr__(self):
        return '[' + ', '.join([repr(c) for c in self.children]) + ']'

    def get_has_run(self):
        if self._has_run:
            return True
        for task in self.children:
            if not task.has_run:
                return False
        return True

    has_run = property(get_has_run, Task.set_has_run)

    @property
    def success(self):
        return all(map(lambda x: x.success, self.children))


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


def sequential(*args):
    raise NotImplementedError
