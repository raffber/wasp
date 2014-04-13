from .node import make_nodes, remove_duplicates, FileNode
from uuid import uuid4 as uuid
from io import StringIO
from .util import run_command, Factory, UnusedArgFormatter
from . import ctx
from .arguments import Argument, ArgumentCollection


class PreviousTaskDb(dict):
    def __init__(self, cache):
        d = cache.getcache('previous-tasks')
        super().__init__(d)
        d.clear()


class TaskDb(dict):
    def __init__(self, cache):
        self._cache = cache

    def save(self):
        d = self._cache.getcache('previous-tasks')
        for key, task in self.items():
            success = task.success
            d[task.identifier] = {'success': success}

    def add(self, task):
        if isinstance(task, Task):
            self[task.identifier] = task
        elif isinstance(task, list):
            for t in task:
                assert isinstance(t, Task), 'Either a list of task or task is required as argument'
                self[t.identifier] = t
        else:
            assert False, 'Either a list of task or task is required as argument'


class Task(object):
    def __init__(self, sources=[], targets=[], children=[], always=False, id_=None):
        self._sources = make_nodes(sources)
        self._targets = make_nodes(targets)
        assert isinstance(children, list)
        self.children = children
        self._has_run_cache = False
        self._always = always
        self._success = False
        self._arguments = ArgumentCollection()
        if id_ is None:
            self._id = uuid()
        else:
            self._id = id_
        if self.has_run:
            # check previous tasks if this task was successful
            # TODO: necessary?
            # TODO: ... ? how?, set target signature valid to false?
            pass

    def _id_from_sources_and_targets(self):
        taskname = self.__class__.__name__
        targets = '-'.join([t.identifier for t in self.targets])
        sources = '-'.join([s.identifier for s in self.sources])
        ret = taskname + ':' + sources + '=>' + targets
        return ret

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
        self._has_run_cache = has_run

    def get_has_run(self):
        if self._has_run_cache:
            return True
        # else, recheck
        if self.always:
            return False
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
        pass

    @property
    def arguments(self):
        return self._arguments

    def use(self, *args, **kw):
        for a in args:
            if isinstance(a, Argument):
                self.use_arg(a)
            elif isinstance(a, Check):
                args = a.arguments
                if args is None:
                    continue
                for a in args:
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

    def require(self, arguments=None, checks=None):
        if arguments is not None:
            if isinstance(arguments, str):
                arguments = [arguments]
            for argname in arguments:
                if not argname in self._arguments:
                    arg = Argument(argname)
                    arg.retrieve_all()
                    self.arguments.add(arg)
        if checks is not None:
            if isinstance(checks, str):
                checks = [checks]
            for checkname in checks:
                if not checkname in ctx.checks:
                    raise MissingCheckError('"{0}" requires you to check for "{1}"'.format(self.__class__.__name__, checkname))


class MissingCheckError(RuntimeError):
    pass


class FindTask(Task):

    always = True

    def run(self):
        pass


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd=''):
        super().__init__(sources=sources, targets=targets, children=children)
        self._cmd = cmd

    @property
    def cmd(self):
        return self._cmd

    def finished(self, exit_code, out, err):
        return exit_code == 0

    def _process_args(self):
        src_list = []
        for s in self.sources:
            if isinstance(s, FileNode):
                src_list.append(s.path)
        tgt_list = []
        for t in self.targets:
            if isinstance(t, FileNode):
                tgt_list.append(t.path)
        src_str = ' '.join(src_list)
        tgt_str = ' '.join(tgt_list)
        kw = {'SRC': src_str,
              'TGT': tgt_str}
        for key, arg in self.arguments.items():
            val = arg.value
            if isinstance(val, list):
                val = ' '.join([str(i) for i in list])
            kw[arg.upperkey] = str(val)
        return kw

    def prepare_args(self, kw):
        return kw

    def format_cmd(self, **kw):
        s = UnusedArgFormatter().format(self.cmd, **kw)
        return s

    def run(self):
        kw = self._process_args()
        kw = self.prepare_args(kw)
        commandstring = self.format_cmd(**kw)
        out = StringIO()
        err = StringIO()
        exit_code = run_command(commandstring, stdout=out, stderr=err)
        self.success = exit_code == 0
        self.has_run = True
        ret = self.finished(exit_code, out.read(), err.read())
        results = []
        if ret is not None:
            if not isinstance(ret, list):
                ret = [ret]
            for r in ret:
                if isinstance(r, bool):
                    self._success = r
                elif isinstance(r, TaskResult):
                    results.append(r)
        return results


class TaskResultCollection(dict):
    def by_name(self, name):
        ret = []
        for result in self:
            if result.name == name:
                ret.append(result)
        return ret

    def add(self, result):
        assert isinstance(result, TaskResult), 'argument must be a class of type TaskResult'
        self[result.identifier] = result

    def to_json(self):
        ret = {}
        for result in self:
            if not isinstance(result, SerializableTaskResult):
                continue
            tojson = result.to_json()
            if tojson is not None:
                ret[result.id] = tojson
        return ret


class TaskResult(object):
    def __init__(self, id_=None):
        if id is None:
            self._id = uuid()
        else:
            self._id = id_

    @property
    def identifier(self):
        return self._id


class SerializableTaskResult(TaskResult):
    def __init__(self, name, id_=None):
        if id_ is None:
            id_ = name
        super().__init__(id_=id_)
        assert isinstance(name, str), 'Name must be given as string!'
        self._name = name

    @property
    def name(self):
        return self._name

    def to_json(self):
        return {'id': self.identifier,
                'name': self.name}

    @staticmethod
    def from_json(cls, d):
        assert 'type' in d, 'Invalid json for TaskResult. No type information present. Delete cache!'
        return task_result_factory.create(d['type'], **d)


class Check(SerializableTaskResult):
    def __init__(self, name, arguments=None, description='', id_=None):
        if id_ is None:
            id_ = name
        super().__init__(name, id_=id_)
        self._description = description
        assert isinstance(arguments, Argument) or isinstance(arguments, list), \
            'Check: arguments must be either of type Argument or a list thereof'
        if isinstance(arguments, Argument):
            arguments = [arguments]
        else:
            for arg in arguments:
                assert isinstance(arg, Argument), \
                    'Check: arguments must be either of type Argument or a list thereof'
        self._arguments = arguments

    @property
    def description(self):
        return self._description

    def to_json(self):
        d = super().to_json()
        d['description'] = self.description
        d['type'] = 'Check'
        # TODO: serialize arguments
        return d

    @property
    def arguments(self):
        return self._arguments

task_result_factory = Factory(SerializableTaskResult)


class register_task_result(object):
    def __init__(self):
        pass

    def __call__(self, cls):
        task_result_factory.register(cls)
        return cls