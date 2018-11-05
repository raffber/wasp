from wasp import Task
from wasp.node import FileNode

try:
    from jinja2 import Template
except ImportError as e:
    raise ImportError('The `templating` extension depends on Jinja2: Install it in order to use it!')


class TemplatingTask(Task):
    def __init__(self, source, target):
        super().__init__(sources=source, targets=target)
        self._templating_src = source

    def _run(self):
        with open(self._templating_src, 'r') as f:
            data = f.read()
        tmplate = Template(data)
        kw = self.arguments.dict()
        processed = tmplate.render(**kw)
        for target in self.targets:
            if not isinstance(target, FileNode):
                continue
            with open(target.path, 'w') as f:
                f.write(processed)
        self.success = True


def template(source, target):
    return TemplatingTask(source, target)