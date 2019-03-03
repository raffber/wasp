from wasp import node
from wasp.execution import Executor, TaskGraph
from wasp.task import Task
from tests import setup_context


class DummyTask(Task):
    def run(self):
        self.success = True


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



