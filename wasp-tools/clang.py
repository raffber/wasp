from wasp import TaskGroup, tool, Task, shell, file, ctx, quote, directory, files
from wasp.util import is_iterable
import json


cpp = tool('cpp')


def _flatten(*tasks):
    ret = []
    for task in tasks:
        if is_iterable(task):
            ret.extend(_flatten(*task))
        elif isinstance(task, TaskGroup):
            ret.extend(_flatten(*task.tasks))
        ret.append(task)
    return ret


def add_compile_db(t):
    t.result['compiledb'] = {
        'directory': ctx.topdir.path,
        'command': t._format_cmd(),
        'file': str(t.arguments.value('csource'))
    }


class CollectCompileDb(Task):

    def __init__(self, dbname):
        self._dir = directory(ctx.builddir.join(dbname))
        self._dbfile = self._dir.join('compile_commands.json')
        super().__init__(targets=self._dbfile, always=True)
        
        self.arguments['compiledb'] = []

    def use_arg(self, arg):
        if arg.name == 'compiledb':
            v = self.arguments.value('compiledb')
            v.append(arg.value)
            return
        super().use_arg(arg)

    def run(self):
        self.log.debug('reading compile db')
        if not self._dir.exists:
            self._dir.mkdir()
        if self._dbfile.exists:
            with open(self._dbfile.path) as f:
                current_db = json.load(f)
        else:
            current_db = []
        data = self.arguments.value('compiledb')
        d_data = {d['file']: d for d in data}
        for v in current_db:
            fpath = v['file']
            if fpath not in d_data:
                d_data[fpath] = v
        self.log.debug('writing compile db')
        with open(self._dbfile.path, 'w') as f:
            json.dump(list(d_data.values()), f)
        self.log.log_success('Updated compile db: ' + self._dbfile.path)
        self.success = True


def compile_db(tasks, dbname):
    if not is_iterable(tasks):
        tasks = [tasks]
    tasks = _flatten(*tasks)
    compile_tasks = []
    for task in tasks:
        if not isinstance(task, cpp.CompileTask):
            continue
        task.run.append(add_compile_db)
        compile_tasks.append(task)
    collector = CollectCompileDb(dbname)
    collector.use(compile_tasks)
    return collector


CHECKS = '*,-llvm-header-guard,-cppcoreguidelines-pro-type-union-access'


def tidy(sources, dbname):
    dirname = directory(ctx.builddir.join(dbname))
    return shell('clang-tidy -checks=' + CHECKS + ' -fix '
            '-header-filter=".*" -p {build_dir} {src}',
            sources=files(sources), always=True
        ).use(build_dir=dirname)
