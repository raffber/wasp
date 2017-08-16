from wasp import shell, Directory, spawn
from wasp.fs import find_exe


def html(docdir):
    sh = shell('{sphinx_build} -b html -d {build_docdir}/doctrees {docdir} {build_docdir}/html'
               , always=True)
    sh.use(build_docdir=Directory(docdir).to_builddir(), docdir=docdir)
    sh.use(spawn(':sphinx/sphinx_build', find))
    sh.require('sphinx_build')
    return sh


def find(produce=True):
    ret = find_exe('sphinx-build', argprefix='sphinx_build')
    if produce:
        ret.produce(':sphinx/sphinx_build')
    return ret
