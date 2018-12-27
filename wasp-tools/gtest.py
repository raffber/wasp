from wasp import tool, Directory, directory, log, CommandFailedError, node, file, shell
from wasp import Logger, osinfo, group

cpp = tool('cpp')


def configure(dir):
    node(':gtest/config').write({'dir': directory(dir)})


def compile(test_src, bd_path=None, scan_ignore=None):
    gtest_dir = node(':gtest/config').read().value('dir', None)
    if gtest_dir is None:
        log.fatal('gtest: You must call configure() to setup the path to the gtest directory')
        raise CommandFailedError()
    if isinstance(test_src, str):
        test_src = [test_src]
    gtest_include = [gtest_dir, gtest_dir.join('include')]
    gtest_src = gtest_dir.join('src/gtest-all.cc')
    test_obj = cpp.compile(test_src, bd_path=bd_path, scan_ignore=scan_ignore).use(includes=gtest_include)
    gtest_obj = cpp.compile(gtest_src, bd_path=bd_path, scan=False).use(includes=gtest_include)
    return group(test_obj, gtest_obj)


def link(objs, target=None):
    if target is None:
        target = 'test-main' + ('.exe' if osinfo.windows else '')
    return cpp.link(objs, target=target)


def run_all(target=None):
    if target is None:
        target = 'test-main' + ('.exe' if osinfo.windows else '')
    ret = shell(file(target).to_builddir().path)
    ret.log = log.clone()
    ret.log.configure(verbosity=Logger.INFO)
    return ret
