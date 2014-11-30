from .task import Task
from .node import FileNode
from .argument import Argument
from .util import UnusedArgFormatter, run_command, Serializable
from . import factory
from io import StringIO


class ShellTask(Task):
    def __init__(self, sources=[], targets=[], children=[], cmd='', always=False):
        super().__init__(sources=sources, targets=targets, children=children, always=always)
        self._cmd = cmd

    @property
    def cmd(self):
        return self._cmd

    def _finished(self, exit_code, out, err):
        return exit_code == 0

    def _process_args(self):
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
        for key, arg in self.arguments.items():
            val = arg.value
            if isinstance(val, list):
                val = ' '.join([str(i) for i in list])
            kw[arg.upperkey] = str(val)
        return kw

    def _prepare_args(self, kw):
        return kw

    def _format_cmd(self, **kw):
        s = UnusedArgFormatter().format(self.cmd, **kw)
        return s

    def _run(self):
        kw = self._process_args()
        kw = self._prepare_args(kw)
        commandstring = self._format_cmd(**kw)
        out = StringIO()
        err = StringIO()
        exit_code = run_command(commandstring, stdout=out, stderr=err)
        print(commandstring + ': ' + str(exit_code))
        self.success = exit_code == 0
        self.has_run = True
        ret = self._finished(exit_code, out.read(), err.read())
        if ret is not None:
            if not isinstance(ret, list) or isinstance(ret, tuple):
                ret = [ret]
            first = True
            for r in ret:
                if first and isinstance(r, bool):
                    self._success = r
                elif isinstance(r, Argument):
                    self._result.add(r)
                # TODO: more...
                first = False


def shell(cmd, sources=[], targets=[], always=False):
    return ShellTask(sources=sources, targets=targets, cmd=cmd, always=always)
