
Welcome To wasp
===============

"wasp" is yet another build tool! It was started as a private research project,
since the author had a vision of build tool that did not exist and wanted to find
out what's so difficult about build tools. wasp was inspired by a lot of tools
that already exist and tries to extract the best ideas from them. Of particular
importance are gradle and waf, but also grunt, ant, scons and cmake have
sparked a lot of ideas.

Features and Non-Features
-------------------------

 * wasp does not invent yet another language: it uses plain python.
   Thus, build scripts are not declarative! But great care was taken while
   designing the API to make sure build scripts read fluently.
   wasp is also a library and build scripts are python modules. It can
   therefore be integrated with other python libraries and nothing is
   obscured from the user. Everything happens explicitly.

 * The wasp-script can be checked into version control systems and
   extracts itself. The only requirement for its use is a python3
   installation. Porting your development environment to another machine
   has never been easier!

 * wasp favors convention over configuration. While everything can be customized,
   a lot of defaults are already in place and make you productive from the start.

 * Since wasp is also library, customization of the build tasks can be done
   on many levels and therefore existing code can be effectively reused.

 * wasp tries to simplify complex tasks and does not focus on simplifying tasks
   that are already simple. As your project grows more complex, so does your build process.
   wasp tries to keep up with the increased complexity by providing few, but powerful
   tools to simplify your build process.
   Since wasp is not limited to a specific set of technologies, it scales with your project.

 * No magic happens: Everything is explicit. What you write happens,
   nothing more and nothing less! For example, this means that no automatic
   scanning of file system access is performed to determine task dependencies and
   that task sources and targets must be defined. Of course, there are abstractions
   which make default choices for you.


wasp is for you if....
----------------------

 * ... you want


wasp is *not* for you if...
-------------------------------------------

 * ... you only have simple tasks to perform. You're probably better of with one
 of the lesser general purpose tools. (e.g. ant for building java stuff
 or QMAKE for building qt apps)

 * ... you have never seen python before and are not willing to
    learn (a very awesome) new programming language.

 * ... using python3 (instead of python2) is somehow impossible/difficult for you.

 * ... if you want something declarative. We strongly believe that declarative
 build tools are the wrong approach.

 * ... you don't care about the quality of your build tooling.
