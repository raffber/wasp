from wasp import node, Node
from wasp.execution import TaskGraph
from wasp.signature import Signature
from wasp.task import Task
from tests import setup_context


class DummyTask(Task):
    def run(self):
        self.success = True


class UnchancedSignature(Signature):
    def __init__(self):
        super().__init__('unchanged')

    def to_json(self):
        return None

    @classmethod
    def from_json(cls, d):
        return cls()

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def clone(self):
        return UnchancedSignature()

    def refresh(self, value=None):
        self._valid = True
        self._value = value


class UnchangedNode(Node):
    def _make_signature(self):
        return UnchancedSignature()


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
    graph.task_completed(p1)
    assert p1 == t1 or p1 == t2
    p1 = graph.pop()
    graph.task_completed(p1)
    assert p1 == t1 or p1 == t2
    p3 = graph.pop()
    assert p3 == t3
    graph.task_completed(p3)


if __name__ == '__main__':
    test_simple_dependencies()
    test_always()
    test_not_run()
