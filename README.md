Welcome To wasp
===============

`wasp` is yet another build tool! It started as a private research project but evolved into
a standalone python based build tool and task automation framework.
`wasp` was inspired by many great tools such as cmake, ant, gradle and many more.

Features and Non-Features
-------------------------

 * wasp does not invent yet another language: it uses plain python.
   Thus, build scripts are not declarative but are executable programs.
   Great care was taken while designing the API to make sure build scripts read fluently.
   wasp is also a library and build scripts are python modules. It can
   therefore be integrated with other python libraries and nothing is
   obscured from the user.

 * The wasp-script can be checked into version control systems and
   extracts itself. The only requirement for its use is a python3
   installation. Deploying your build tool is therefore really easy.

 * `wasp` favors convention over configuration. While everything can be customized,
   a lot of defaults are already in place and make you productive from the start.

 * Since wasp is also library, customization of the build tasks can be done
   on many levels and therefore existing code can be effectively reused. Think of
   your build scripts as programs and not as configuration.

 * wasp tries to simplify complex tasks and does not focus on simplifying tasks
   that are already simple. As your project grows more complex, so does your build process.
   wasp tries to keep up with the increased complexity by providing few, but powerful
   tools to simplify your build process.
   Since wasp is not limited to a specific set of technologies, it scales with
   your project and the number of technologies you use.

 * No magic happens: Everything is explicit. For example, this means that no automatic
   scanning of file system access is performed to determine task dependencies and
   that task sources and targets must be defined. Of course, there are abstractions
   and conventions which make default choices for you and automatically define dependencies
   between your tasks.


wasp is for you if....
----------------------

 * you want flexible build tool for automating a large number of build tasks

 * if you don't use a single technology with one associated set of tooling,
    but multiple technologies and tools that need to interact.

 * you want to be able to create a build system that can be easily deployed on many platforms.

 * you want to integrate multiple projects each with individual build tools into one large project.


wasp is *not* for you if...
----------------------------

 * you only have trivial tasks to perform. You're probably better of with one
    of the less general purpose tools.

 * you have never seen python before and are not willing to
    learn (a very awesome) new programming language.

 * using python3 (instead of python2) is somehow impossible/difficult for you.

 * if you want something declarative. The fact that `wasp` is not declarative was a
    very delibrate design descision.
