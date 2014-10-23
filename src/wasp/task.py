from .node import make_nodes
from uuid import uuid4 as uuid
from .util import Factory, Serializable, CallableList
from .arguments import Argument, ArgumentCollection
from .logging import Logger
from functools import reduce
import operator


class Task(object):
    def __init__(self, sources=[], targets=[], children=[], always=False, identifier=None):
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
            self._id = str(uuid())
        else:
            self._id = identifier
        self._run_list = CallableList().arg(self)
        self._run_list.append(self._run)
        self._initialize_list = CallableList().arg(self)
        self._initialize_list.append(self._initialize)
        self._prepare_list = CallableList().arg(self)
        self._prepare_list.append(self._prepare)
        self._success_list = CallableList().arg(self)
        self._success_list.append(self._success)
        self._fail_list = CallableList().arg(self)
        self._fail_list.append(self._fail)
        self._postprocess_list = CallableList().arg(self)
        self._postprocess_list.append(self._postprocess)
        self._spawn_list = CallableList().arg(self).collect(lambda ret: reduce(operator.add, ret))
        self._spawn_list.append(self._spawn)
        self._logger = Logger()

    @property
    def logger(self):
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

    @property
    def initialize(self):
        return self._initialize_list

    def _initialize(self):
        pass

    @property
    def prepare(self):
        return self._prepare_list

    def _prepare(self):
        pass

    @property
    def success(self):
        return self._success_list

    def _success(self):
        pass

    @property
    def fail(self):
        return self._fail_list

    def _fail(self):
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
        pass

    @property
    def targets(self):
        return self._targets

    def set_has_run(self, has_run):
        self._has_run = has_run

    def get_has_run(self):
        # returns true if all source and target file signatures were unchanged
        # from the last run and all child-tasks have successfully
        # run.
        # note that each task may change the file signatures
        # of its targets, as such, it can not be assuemd
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
        self._has_run_cache = True
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
            elif isinstance(a, str):
                arg = Argument(a).retrieve_all()
                self.use_arg(arg)
            elif isinstance(a, list):
                self.use(*a)
        for k, a in kw.items():
            self.use_arg(Argument(k).assign(a))

    def use_arg(self, arg):
        for c in self.children:
            c.use_arg(arg)
        self.arguments.add(arg)

    def require(self, arguments=None):
        if arguments is not None:
            if isinstance(arguments, str):
                arguments = [arguments]
            for argname in arguments:
                # TODO: also retireve from ctx.arguments
                if not argname in self._arguments:
                    arg = Argument(argname)
                    arg.retrieve_all()
                    if arg.value is None:
                        # TODO: ....
                        raise RuntimeError('AAAAAAAAH! TODO!')
                    self.arguments.add(arg)


class TaskGroup(Task):
    def __init__(self, children):
        # TODO: think about this again and write it in less lines
        # this should all be O(n+m) assuming n is the total number of sources
        # and m is the total number of targets
        # flatten sources and targets first
        sources = []
        for c in children:
            sources.extend(self._recursive_flatten_sources(c))
        targets = []
        for c in children:
            targets.extend(self._recursive_flatten_targets(c))
        # create a dict mapping from identifier to node
        source_dict = {}
        for s in sources:
            source_dict[s.identifier] = s
        targets_new = []
        for t in targets:
            # remove source node if it is also a target
            # otherwise, the target node in question is external
            # and the source node is external as well.
            if t.identifier in source_dict:
                del source_dict[t.identifier]
            else:
                targets_new.append(t)
        super().__init__(children=children, always=True)

    def _recursive_flatten_sources(self, task):
        ret = list(task.sources)
        for c in task.children:
            ret.extend(self._recursive_flatten_sources(c))
        return ret

    def _recursive_flatten_targets(self, task):
        ret = list(task.targets)
        for c in task.children:
            ret.extend(self._recursive_flatten_targets(c))
        return ret


def group(*args):
    if len(args) == 1 and isinstance(args, list):
        return group(*args)
    for arg in args:
        assert isinstance(arg, Task), '*args must be a list of Tasks'


task_factory = Factory(Serializable)


class register_task(object):
    def __init__(self, cls):
        assert issubclass(cls, Serializable)
        task_factory.register(cls)