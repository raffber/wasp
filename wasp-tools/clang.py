from wasp import TaskGroup, tool, Task, shell, file, ctx
import json
from collections import Iterable


cpp = tool('cpp')


def _flatten(*tasks):
    ret = []
    for task in tasks:
        if isinstance(task, Iterable):
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

    def _init(self):
        self.arguments['compiledb'] = []

    def use_arg(self, arg):
        if arg.name == 'compiledb':
            v = self.arguments.value('compiledb')
            v.append(arg.value)
            return
        super().use_arg(arg)

    def run(self):
        self.log.debug('reading compile db')
        with open('compile_commands.json') as f:
            current_db = json.load(f)
        data = self.arguments.value('compiledb')
        d_data = {d['file']: d for d in data}
        for v in current_db:
            fpath = v['file']
            if fpath not in d_data:
                d_data[fpath] = v
        self.log.debug('writing compile db')
        with open('compile_commands.json', 'w') as f:
            json.dump(list(d_data.values()), f)
        self.log.log_success('Successfully updated compile db')
        self.success = True


def compile_db(tasks):
    compile_db = file('compile_commands.json')
    if not compile_db.exists:
        with open(compile_db.path, 'w') as f:
            f.write('[]')
    tasks = _flatten(*tasks)
    compile_tasks = []
    for task in tasks:
        if not isinstance(task, cpp.CompileTask):
            continue
        task.run.append(add_compile_db)
        compile_tasks.append(task)
    collector = CollectCompileDb(always=True, targets=compile_db)
    collector.use(compile_tasks)
    return collector.produce(':clang/compiledb')


CHECKS = '*,-llvm-header-guard'


def tidy(src, directory):
    return shell('clang-tidy -checks=' + CHECKS + '-header-filter="{dir}/.*" {src}',
                    sources=[src, 'compile_commands.json']).use(
                    ':clang/compiledb', dir=directory)
