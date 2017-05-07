from wasp import tool, Directory, directory, log, CommandFailedError, node

cpp = tool('cpp')


def configure(dir):
    node(':gtest/config').write({'dir': directory(dir)})


def compile(test_src):
    gtest_dir = node(':gtest/config').read().value('dir', None)
    if gtest_dir is None:
        log.fatal('gtest: You must call configure() to setup the path to the gtest directory')
        raise CommandFailedError()
    test_src = list(test_src)
    gtest_include = [gtest_dir, gtest_dir.join('include')]
    gtest_src = gtest_dir.join('src/gtest-all.cc')
    test_src.append(gtest_src)
    test_obj = cpp.compile(test_src).use(includes=gtest_include)
    return test_obj

def link(objs, target='test-main'):
    return cpp.link(objs, target=target)

def run_all(target='test-main'):
    pass
