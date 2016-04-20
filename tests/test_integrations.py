from wasp import osinfo, directory, ctx
from wasp.shell import run


def check_exists():
    for exe in ['dmd', 'npm', 'rustc', 'cargo', 'gcc', 'moc']:
        if not directory('/usr/bin').join(exe).exists:
            return False
    return True


def test_build():
    if not osinfo.linux or not check_exists():
        return
    topdir = directory(__file__).join('..').absolute
    directory(topdir.join('build')).remove()
    exit_code, proc_out = run('./wasp build', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    err_lines = proc_out.stderr.split('\n')
    # check if the commands succeeded
    assert '[SUCC]  Command: `configure`' in out_lines
    assert '[SUCC]  Command: `build`' in out_lines
    # check if dmd was used
    assert any('dmd' in l for l in out_lines)
    # check if jsmin was installed by npm
    assert any('jsmin@' in l for l in out_lines)
    bd = directory(topdir.join('build'))
    assert bd.join('main').exists
    assert bd.join('buildtest').exists
    assert bd.join('node_modules').exists
    main_file = bd.join('main').path
    exit_code, proc_out = run(main_file)
    out = proc_out.stdout.split('\n')
    assert 'Hello, World!!' in out
    assert bd.join('node_modules/jsmin/bin/jsmin').exists


def test_nodebuild():
    if not osinfo.linux or not check_exists():
        return


def test_rustbuild():
    if not osinfo.linux or not check_exists():
        return


if __name__ == '__main__':
    test_build()