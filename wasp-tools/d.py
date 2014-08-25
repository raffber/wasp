import wasp
from wasp import ShellTask, FindTask, ctx, Task

#
# @wasp.configure
# def configure():
#     return FindDCompiler()
#
#
# class DTask(ShellTask):
#     def prepare(self):
#         self.require(checks='dc', arguments='dc')
#
#
# class DCompile(DTask):
#     def __init__(self, fpath):
#         self.object_file = ctx.builddir.join(fpath, append='.o')
#         super().__init__(sources=fpath, targets=self.object_file)
#
#     cmd = '{DC} {DFLAGS} -c {SRC} -of{TGT}'
#
#
# class DLink(DTask):
#     def __init__(self, sources, binary_name):
#         self.binary = ctx.builddir.join(binary_name)
#         super().__init__(sources=sources, targets=self.binary)
#
#     cmd = '{DC} {LDFLAGS} {SRC} -of{TGT}'
#
#
# class DProgram(Task):
#     def __init__(self, sources, program_name):
#         if not isinstance(sources, list):
#             sources = [sources]
#         children = [DCompile(src) for src in sources]
#         objs = [c.object_file for c in children]
#         children.append(DLink(objs, program_name))
#         super().__init__(children=children)
#
#
# class FindDCompiler(FindTask):
#     def run(self):
#         # TODO: actually check for /usr/bin/dmd
#         dc = wasp.Argument('dc').assign('/usr/bin/dmd')
#         ret = wasp.Check('dc',arguments=dc, description='Checks for the D-comiler and sets DC')
#         self.success = True
#         return ret