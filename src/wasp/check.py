from .task import SerializableTaskResult
from . import ctx


class Check(SerializableTaskResult):
    def __init__(self, name, arguments=None, description='', id_=None):
        if id_ is None:
            id_ = name
        super().__init__(name, id_=id_)
        self._description = description
        self._arguments = arguments

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
        return self._arguments


def override_check(name, arguments=None, description=''):
    chk = Check(name, arguments=arguments, description=description)
    ctx.checks.add(chk)
    return chk