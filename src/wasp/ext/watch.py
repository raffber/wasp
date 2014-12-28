from wasp import Command, extensions, ExtensionMetadata, Task, Argument, TaskCollection
from wasp.util import Event
from wasp.main import run_command, execute_tasks
from wasp.decorators import decorators
from wasp import osinfo, log
from wasp.execution import execute

import os
import re


try:
    import pyinotify

    class MonitorDaemon(object):

        class Handler(pyinotify.ProcessEvent):
            _callback = None
            _files = None
            _regexp = None

            def process_default(self, event):
                if self._callback is None:
                    return
                if event.pathname in self._files or self._regexp.match(event.name):
                    self._callback()

            def my_init(self, callback=None, files=None, regexp=None):
                if regexp is None:
                    regexp = '.*'
                self._regexp = re.compile(regexp)
                self._callback = callback
                assert files is not None
                self._files = files

        def __init__(self, files, command='build', regexp=None, directory=None):
            self._regexp = regexp
            self._watchmanager = pyinotify.WatchManager()
            self._dir = directory
            self._files = [os.path.abspath(f) for f in files]
            self._dirs = set([os.path.dirname(f) for f in self._files])
            if self._dir is not None:
                self._dirs.add(self._dir)
            self._command = command
            self.files_changed_event = Event()

        def run(self):
            for d in self._dirs:
                # would it be better to watch  IN_CLOSE_WRITE?! maybe sth leaves a file permanently
                # open, such as a log file => no CLOSE_WRITE event is triggered
                # what about IN_CREATE?!
                self._watchmanager.add_watch(d, mask=pyinotify.IN_MODIFY | pyinotify.IN_MOVED_TO)
            handler = MonitorDaemon.Handler(callback=self._files_changed, files=self._files, regexp=self._regexp)
            notifier = pyinotify.Notifier(self._watchmanager, handler)
            try:
                notifier.loop()
            except KeyboardInterrupt:
                notifier.stop()

        def _files_changed(self):
            self.files_changed_event.fire()
            run_command(self._command)

    class watch(object):
        def __init__(self, *files, command='build', directory=None, regexp=None):
            self._monitor = MonitorDaemon(files, command=command, regexp=regexp, directory=directory)
            self._f = None

        def __call__(self, f):
            self._monitor.files_changed_event.connect(f)
            self._f = f
            decorators.commands.append(Command('watch', self.command_fun, description='Launches a background daemon'
                                                                        ' which monitors the file system for changes and'
                                                                        'runs appropriate commands.'))
            return f

        def command_fun(self):
            assert self._f is not None
            tasks = TaskCollection(self._f())
            execute_tasks('watch', tasks)
            self._monitor.run()


except ImportError as e:
    if osinfo.linux:
        log.warn('`daemon` extension requires the pyinotify package, which is not installed. Please install it.')
    else:
        log.warn('`daemon` extension is not available on your platform')

    class MonitorDaemon(object):
        def __init__(self, files, command='build'):
            pass

        def run(self):
            pass

    class watch(object):
        def __init__(self, *files, command='build', directory=None, regexp=None):
            pass

        def __call__(self, f):
            return f


class DaemonMetadata(ExtensionMetadata):
    wants = []
    requires = []
    name = 'watch'
    description = 'Monitors file system changes and allows running commands for it.'
    author = 'Raphael Bernhard <beraphae@gmail.com>'
    website = None
    documentation = None

extensions.register(extension=None, meta=DaemonMetadata())