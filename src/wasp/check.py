from .task import SerializableTaskResult
from .arguments import Argument
from . import ctx


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


def override_check(name, arguments=None, description=''):
    chk = Check(name, arguments=arguments, description=description)
    ctx.checks.add(chk)
    return chk