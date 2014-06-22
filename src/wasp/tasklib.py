from .task import Task
from os import remove as remove_file


class RemoveFileTask(Task):
    always = True

    def __init__(self, sources):
        assert isinstance(sources, list) or isinstance(sources, str), 'sources must be a string or a list thereof'
        if isinstance(sources, str):
            sources = [sources]
        super().__init__(sources=sources)

    def run(self):
        for s in self.sources:
            remove_file(s)
