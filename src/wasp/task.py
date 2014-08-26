from .node import make_nodes
from uuid import uuid4 as uuid
from .util import Factory, Serializable
from .arguments import Argument, ArgumentCollection


class Task(object):
    def __init__(self, sources=[], targets=[], children=[], always=False, identifier=None):
        self._sources = make_nodes(sources)
        self._targets = make_nodes(targets)
        assert isinstance(children, list)
        self.children = children
        self._has_run = False
        self._always = always
        self._success = False
        self._arguments = ArgumentCollection()
        if id_ is None:
            self._id = str(uuid())
        else:
            self._id = identifier

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

    def prepare(self):
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

    def run(self):
        self._success = True

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


task_factory = Factory(Serializable)


class register_task(object):
    def __init__(self, cls):
        assert issubclass(cls, Serializable)
        task_factory.register(cls)