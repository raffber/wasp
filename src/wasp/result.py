from . import ctx
from uuid import uuid4 as uuid
from .util import Serializable, Factory


class TaskResultCollection(dict):
    def by_name(self, name):
        ret = []
        for result in self:
            if not isinstance(result, SerializableTaskResult):
                continue
            if result.name == name:
                ret.append(result)
        return ret

    def add(self, result):
        if isinstance(result, list):
            for res in result:
                self.add(res)
            return
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

    def load(self, serialized):
        for key, value in serialized.items():
            self[key] = task_result_factory.create(value['type'], **value)

    def save(self):
        serialized = self.to_json()
        cached_results = ctx.cache.getcache('results')
        for key in serialized.keys():
            cached_results[key] = serialized[key]


class TaskResult(object):
    def __init__(self, id_=None):
        if id is None:
            self._id = uuid()
        else:
            self._id = id_

    @property
    def identifier(self):
        return self._id


class SerializableTaskResult(TaskResult, Serializable):
    pass

task_result_factory = Factory(SerializableTaskResult)


class register_task_result(object):
    def __call__(self, cls):
        assert isinstance(cls, SerializableTaskResult)
        task_result_factory.register(cls)
        return cls