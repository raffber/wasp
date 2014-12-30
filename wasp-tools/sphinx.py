from wasp import shell, Directory
from wasp.fs import FindExecutable


def html(docdir):
    sh = shell('{sphinx_build} -b html -d {build_docdir}/doctrees {docdir} {build_docdir}/html'
               , always=True)
    sh.use(build_docdir=Directory(docdir).to_builddir(), docdir=docdir)
    sh.require('sphinx_build')
    return sh


def find():
    return FindExecutable('sphinx-build', argprefix='sphinx_build')
