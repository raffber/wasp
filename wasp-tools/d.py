from wasp import *


@configure
def configure():
    return FindD()


class DTask(ShellTask):
    def prepare(self):
        if not 'd' in ctx.checks:
            raise MissingCheckError('The d-check has never been run')
        if 'DC' not in self.arguments:
            arg = Argument('dc').retrieve_all()
            self.arguments.add(arg)


class DCompile(DTask):
    def __init__(self, fpath):
        self.object_file = ctx.builddir.join(fpath, append='.o')
        super().__init__(sources=fpath, target=self.object_file)

    cmd = '{DC} {DFLAGS} -c {SRC} {TGT}'


class DLink(DTask):
    def __init__(self, sources, binary_name):
        self.binary = ctx.builddir.join(binary_name)
        super().__init__(sources=sources, target=self.binary)

    cmd = '{DC} {LDFLAGS} {SRC} {TGT}'


class DProgram(DTask):
    def __init__(self, sources, program_name):
        children = [DCompile(src) for src in sources]
        objs = [c.object_file for c in children]
        children.append(DLink(objs, program_name))
        super().__init__(children=children)


class FindD(FindTask):
    def run(self):
        print('FindD!!')
        self.success = True