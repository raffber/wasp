from .node import make_nodes, remove_duplicates, FileNode
from uuid import uuid4 as uuid
from io import StringIO
from .util import run_command, Factory, UnusedArgFormatter
from . import ctx
from .arguments import Argument


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
                assert isinstance(task, Task), 'Either a list of task or task is required as argument'
                self[task.identifier] = t
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
        self._result = None
        self._sources_cache = None
        self._success = False
        self._arguments = []
        if id_ is None:
            self._id = self._id_from_sources_and_targets()
        else:
            self._id = id_
        if self.has_run:
            # check previous tasks if this task was successful
            d = ctx.previous_tasks.get(self._id)
            if d is not None:
                self.success = d.get('success')

    def _id_from_sources_and_targets(self):
        return ('-'.join([s.identifier for s in self.sources])
                + '=>' + '-'.join([t.identifier for t in self.targets]))

    @property
    def always(self):
        return self._always

    @property
    def sources(self):
        if self._sources_cache is not None:
            return self._sources_cache
        ret = []
        for task in self.children:
            ret.extend(task.sources)
        ret.extend(self._sources)
        ret = remove_duplicates(ret)
        self._sources_cache = ret
        return ret

    def __eq__(self, other):
        return other.identfier == self._id

    def __ne__(self, other):
        return not (other.identfier == self._id)

    def prepare(self):
        pass

    def finish(self, result):
        self._has_run_cache = True
        self._result = result

    @property
    def targets(self):
        # TODO: targets cache
        ret = []
        for task in self.children:
            ret.extend(task.targets)
        ret.extend(self._targets)
        return remove_duplicates(ret)

    def set_has_run(self, has_run):
        self._has_run_cache = has_run

    def get_has_run(self):
        if self._has_run_cache:
            return True
        if self.always:
            return False
        # check if all children have run
        for task in self.children:
            if not task.has_run():
                return False
        previous_task = ctx.previous_tasks.get(self.identifier, None)
        if previous_task is None:
            return False
        if not previous_task['success']:
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

    def set_result(self, result):
        self._result = result

    def get_result(self):
        return self._result

    result = property(get_result, set_result)

    def set_success(self, suc):
        self._success = suc

    def get_success(self):
        return self._success

    success = property(get_success, set_success)

    def run(self):
        raise NotImplementedError

    @property
    def arguments(self):
        return self._arguments

    def use(self, *args, **kw):
        for a in args:
            if isinstance(a, Argument):
                self.arguments.append(a)
            elif isinstance(a, Check):
                args = a.arguments
                if args is None:
                    continue
                for a in args:
                    self.arguments.append(a)
            elif isinstance(a, str):
                arg = Argument(a).retrieve_all()
                self.arguments.append(arg)
            elif isinstance(a, list):
                self.use(*a)
        for k, a in kw.items():
            self.arguments.append(Argument(k).assign(a))


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd=''):
        super().__init__(sources=sources, targets=targets, children=children)
        self._cmd = cmd

    @property
    def cmd(self):
        return self._cmd

    def finished(self, exit_code, out, err):
        self.has_run = True
        return None

    def _process_command_string(self, cmd_str):
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
        for arg in self.arguments:
            kw[arg.upperkey] = str(arg.value)
        s = UnusedArgFormatter().format(cmd_str, **kw)
        print(s)
        return s

    def run(self):
        commandstring = self.cmd
        commandstring = self._process_command_string(commandstring)
        out = StringIO()
        err = StringIO()
        exit_code = run_command(commandstring, stdout=out, stderr=err)
        self.success = exit_code == 0
        ret = self.finished(exit_code, out.read(), err.read())
        if ret is not None:
            self._result = ret
        print('HERE!!!')


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
    def __init__(self, success, name, id_=None):
        if id_ is None:
            id_ = name
        super().__init__(success, id_=id_)
        self._name = name

    @property
    def name(self):
        return self._name

    def to_json(self):
        return {'id': self.identifier,
                'success': self.success,
                'name': self.name}

    @staticmethod
    def from_json(cls, d):
        assert 'type' in d, 'Invalid json for TaskResult. Delete cache'
        return task_result_factory.create(d['type'], **d)


class Check(SerializableTaskResult):
    def __init__(self, success, name, description='', id_=None):
        if id_ is None:
            id_ = name
        super().__init__(success, name, id_=id_)
        self._description = description

    @property
    def description(self):
        return self._description

    def to_json(self):
        d = super().to_json()
        d['description'] = self.description
        d['type'] = 'Check'
        return d

    @property
    def arguments(self):
        return None

task_result_factory = Factory(SerializableTaskResult)


class register_task_result(object):
    def __init__(self):
        pass

    def __call__(self, cls):
        task_result_factory.register(cls)
        return cls