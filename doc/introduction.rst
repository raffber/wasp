Introduction
============

``wasp`` is a build tool and build scripts are written in python.


Installation
------------

Be sure to have python3 installed. It is the only dependency of ``wasp``.
Note that python2 is not going to work, ``wasp`` is not backwards
compatible with python2 and is probably never going to be.

Let's get gstarted: ``cd`` into the project directory::

    $ cd path/to/project/directory
    $ wget https://raw.githubusercontent.com/raffber/wasp/master/wasp

``wasp`` extracts itself once you execute it for the first time.
If you upgrade it to a new version, it will automatically upgrade itself.


Your first build script
-----------------------

Now, create your first build script, called ``build.py`` in the same directory::

    import wasp

    @wasp.build
    def build():
        print('hello, world!')

Now run::

    $ ./wasp build
    hello, world!

What you see here is ``wasp`` executing a **Command** called "build".
For the time being, this command just prints "hello, world!".

A command may specify **dependencies** which are commands to be executed
before this specific command. One command may consist of multiple
handler functions, such that you can split the work between mutliple
functions and scripts. You can also invent your own command names and dependencies::

    import wasp

    @wasp.command('run', depends='build')
    def run():
        print('Run my program here!')

Tasks
------

One can think of a build system as a set of ``Tasks`` which have inputs
 (called "sources") and outputs (called ``targets``).


Now, let's do something else, which is not at all useful but demonstrates how
``Tasks`` work::


    import wasp
    from wasp import shell, ctx, file

    @wasp.build
    def build():
        source = file('build.py')
        target = source.to_builddir()
        yield shell('cp {SRC} {TGT}', sources=source, targets=target)

The ``shell()`` function creates a ``Task``, which runs a command (in this case ``cp``) on the shell.

Nodes
-----

Sources and targets are represented as nodes.
Each task defines a set of input and output nodes (called sources and targets).
These nodes point to some data, which may be used by the tasks, thus, the nodes
define a data dependency between the tasks which is used internally by wasp to
parallelize the execution of tasks.

Each time a task is executed, it is recorded which "state" the data of all source
and target nodes is in. If the state of either source or target nodes has changed,
the task is rerun.

There are two different kinds of nodes that are worth mentioning:
 * ``FileNode``: Points to a file and captures its state by a checksum
    across its data. These nodes are implicitly generated by a path to a file.
 * ``SymbolicNode``: A node which contains data in the form of ``Argument``
    items. It is implicitly generated by strings starting with a colon, e.g. ':config'.
    These nodes are used to pass information between tasks, such as which compiler
    to use.

Of course, tools (see :ref:`tools`) may define arbitrary types of nodes.
However, usually, these two basic node types are sufficient.

Creations of nodes is facilitated by calling the ``node()`` (to create a single node)
or the ``nodes()`` functions (to create multiple). The constructor of ``Task`` attempts
to automatically convert the ``sources`` and ``targets`` argument into nodes by calling
the ``nodes()`` function. This is why the following two lines from our example::

        source = file('build.py')
        target = source.to_builddir()

which actually create two ``File`` objects (refer to the :ref:`fs` section) are converted
into ``FileNode`` object.
Refer to the API documentation (TODO:...) for more details.


.. _arguments:

Arguments
---------

While some information may defined while creating tasks, some information is only
known while executing tasks (see :ref:`lifecycle`).
This information is transfered between tasks as so called ``Argument`` objects.
These are just key-value-parirs, where the value must be a json serializable type
(refer to :ref:`utility_json`).

Tasks can ``use()`` arguments, which makes them accessible during task execution
time using the ``task.arguments`` field.
A task ``task1`` may also pass information to another task ``task2`` using the ``task.result`` field.
This dependency is defined by calling ``task2.use(task1)``.
All arguments in ``task1.result`` will be available in ``task2.arguments``.
``task.arguments`` as well as ``task.result`` are ``ArgumentCollection`` objects, which
are dict-like and use the argument name as key.


.. _lifecycle:

Lifecycle  of as Build Process
------------------------------

A build process may be roughly divided into the following stages:

 *  Import of all modules. All build scripts are python modules.
 *  Execution of functions registered with ``@wasp.init``. Here one may run initialization tasks.
 *  Sourcing of command line arguments using function registered with ``@wasp.options``.
 *  Calling of all function registered with ``@wasp.handle_options`` used for postprocessing
    command line arguments. Refer to :ref:`options` for more information on how to present
    command line arguments to a user.
 *  Running all task handler functions (e.g. all functions handling the ``build`` command)
    These functions will typically lead to a set of tasks to be executed.
 *  Execution Phase: All tasks are executing while respecting their data dependencies.
    Usually this is parallelize to reduce build times.
    While executing, all changes to relevant node signatures are recorded.
 *  Last but not least, all results are saved, in particular the signatures of all nodes,
    such that ``wasp`` knows which tasks do not need to be rerun during the next execution.


Passing Arguments between Tasks
-------------------------------


Configuration of tasks may happen during creation time of the
tasks or in the execution phase (see :ref:`lifecycle`).
While the user has influence about the creation order of tasks the execution
engine schedules tasks upon requirement during the execution phase.
Since some configuration data may only be available during execution (e.g. because it
was generated by some other task), one must be able to pass data between tasks.

First of, note that each task contains a:
 *  ``task.arguments`` field, which stores the ``Argument`` objects to be
    during the tasks execution
 *  ``task.result`` field, which stores ``Argument`` objects which are passed on
    to other nodes, which are defined as targets of this task.
    Thus, the contents of ``task.results`` indirectly gets forwarded to other tasks
    futher down in the dependency chain.`

A task provides a generic ``task.use()`` function which, depending on the arguments given,
reacts differently:

 *  If an ``Argument`` object is passed, the argument is sourced to ``task.arguments``.
 *  ``SymbolicNode``: Adds the node as a dependency and retrieves arguments from it.
 *  ``Node``: Adds the node as a dependency.
 *  ``Task``: Adds the task as a dependency of the task by creating an intermediate node.
 *  ``str``: If formatted as a valid identifier for a ``SymbolicNode`` uses the node it points to.
    Otherwise, an empty argument is added and it is attempted to fill it automatically (by calling ``Argument.retrieve_all()``).
 *  ``ArgumentCollection`: The task uses all contained arguments within the collection.
 *  ``TaskGroup``: Uses ``group.target_task`` if given, otherwise all tasks contained in the task group.
 *  Also accepts an iterable objects of the above types.


Further Reading
---------------

 *  File system operations and tasks :ref:`fs`
 *  How to write ``wasp-tools`` :ref:`tools`
 *  A more detailed guide on tasks and how to customize them: :ref:`tasks`
 *  Handling command line options: :ref:`options`
 *  The utility module that ships with ``wasp``: :ref:`utility`


