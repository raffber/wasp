from wasp import Command, extensions, ExtensionMetadata, TaskCollection
from wasp.main import execute_tasks
from wasp import decorators
from wasp import osinfo, log

import os
import re
from wasp.util import is_iterable


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

        def __init__(self, files=None, regexp=None, dirs=None, callback=None):
            self._regexp = regexp
            self._watchmanager = pyinotify.WatchManager()
            if files is not None:
                self._files = [os.path.abspath(f) for f in files]
            else:
                self._files = []
            self._dirs = set([os.path.dirname(f) for f in self._files])
            if dirs is not None:
                if is_iterable(dirs) and not isinstance(dirs, str):
                    for x in dirs:
                        self._dirs.add(x)
                else:
                    self._dirs.add(dirs)
            self._callback = callback
            assert self._callback is not None

        def run(self):
            for d in self._dirs:
                # would it be better to watch  IN_CLOSE_WRITE?! maybe sth leaves a file permanently
                # open, such as a log file => no CLOSE_WRITE event is triggered
                # what about IN_CREATE?!
                self._watchmanager.add_watch(d, mask=pyinotify.IN_MODIFY | pyinotify.IN_MOVED_TO)
            handler = MonitorDaemon.Handler(callback=self._callback, files=self._files, regexp=self._regexp)
            notifier = pyinotify.Notifier(self._watchmanager, handler)
            try:
                notifier.loop()
            except KeyboardInterrupt:
                notifier.stop()

    class watch(object):
        def __init__(self, files=None, dirs=None, regexp=None, command='watch'):
            self._monitor = MonitorDaemon(files=files, regexp=regexp, dirs=dirs, callback=self._callback)
            self._f = None
            self._command = command

        def __call__(self, f):
            self._f = f
            decorators.commands.append(Command(self._command, self.command_fun, description='Launches a background daemon'
                                                                        ' which monitors the file system for changes and'
                                                                        'runs appropriate commands.'))
            return f

        def _callback(self):
            assert self._f is not None
            tasks = TaskCollection(self._f())
            execute_tasks(self._command, tasks)

        def command_fun(self):
            self._callback()
            self._monitor.run()


except ImportError as e:
    if osinfo.linux:
        log.warn('`daemon` extension requires the pyinotify package, which is not installed. Please install it.')
    else:
        log.warn('`daemon` extension is not available on your platform!')

    class MonitorDaemon(object):
        def __init__(self, files=None, regexp=None, dirs=None, callback=None):
            pass

        def run(self):
            pass

    class watch(object):
        def __init__(self, files=None, dirs=None, regexp=None, command='watch'):
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