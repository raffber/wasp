from wasp import node, Node
from wasp.execution import TaskGraph
from wasp.signature import UnchangedSignature
from wasp.task import Task
from tests import setup_context


class DummyTask(Task):
    def run(self):
        self.success = True


class UnchangedNode(Node):
    def _make_signature(self):
        return UnchangedSignature()


def test_always():
    setup_context()
    t = DummyTask()
    graph = TaskGraph([t])
    assert graph.pop() == t
    t = DummyTask()
    n = UnchangedNode()
    t.use(n)
    t.always = True
    graph = TaskGraph([t])
    assert graph.pop() == t


def test_not_run():
    t = DummyTask()
    n = UnchangedNode()
    t.use(n)
    graph = TaskGraph([t])
    assert graph.pop() is None


def test_simple_dependencies():
    setup_context()
    n1 = node()
    n2 = node()
    n3 = node()
    n4 = node()
    t1 = DummyTask().use(n1).produce(n3)
    t2 = DummyTask().use(n2).produce(n4)
    t3 = DummyTask().use(n3, n4)
    tasks = [t1, t2, t3]
    graph = TaskGraph(tasks, ns='foons')
    p1 = graph.pop()
    graph.task_completed(p1, True)
    assert p1 == t1 or p1 == t2
    p1 = graph.pop()
    graph.task_completed(p1, True)
    assert p1 == t1 or p1 == t2
    p3 = graph.pop()
    assert p3 == t3
    graph.task_completed(p3, True)


if __name__ == '__main__':
    test_simple_dependencies()
    test_always()
    test_not_run()
