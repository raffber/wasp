Configuration Files
====================

``wasp`` allows you to configure certain settings in a declarative (JSON) config
file, instead of build scripts. The following values are valid:

* ``extensions``: a list of names of extensions to be loaded
* ``metadata``: Allows specifying a dict with metadata to the project, such as:

    * ``projectname``: Name of the project in descriptions and texts.
    * ``projectid``: Identifier of the project to be used in file names and
      similiar strings. Same as ``projectname`` if not specified.

* ``pythonpath``: List paths to be inserted at the beginning of ``PYTHONPATH``.
  Allows customizing load path of modules.
* ``verbosity``: One of {"quiet", "fatal", "error", "warn", "info", "debug"}.
* ``default_command``: Command to be run if ``./wasp`` is executed without command.
* ``pretty``: Boolean value defining if a pretty printing should be activated.
* ``arguments``: Dict with {"key": "value"} pairs, defining :class:`Argument`
  objects to be inserted into ``ctx.arguments``.


Config file names and priorities
---------------------------------

The top directory is searched for the files ``wasprc.json`` and ``wasprc.user.json``.
Note that values in ``wasprc.user.json`` override values in the ``wasprc.json``.
A typical use-case is the following:

 * In ``wasprc.json`` configure all necessary information for the build system
   to work. Check this file into your version control system.
 * Allow users of your project to override specific values using the file
   ``wasprc.user.json`` and ignore it in your version control system. This
   allows developers to have their custom configurations without touching
   the rest of the build system.


Examples
--------

A typical configuration file could look like this::

    {
        "metadata" : {
            "projectname": "myproject"
        },
        "arguments": {
            "CFLAGS": "-g -O0"
        },
        "verbosity": "info",
        "default_command": "build",
        "extensions": ["templating"]
    }
