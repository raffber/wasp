from wasp import osinfo, directory
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
    main_file = bd.join('main').absolute
    assert main_file.exists
    assert bd.join('buildtest').exists
    assert bd.join('node_modules').exists
    exit_code, proc_out = run(main_file.path)
    out = proc_out.stdout.split('\n')
    assert 'Hello, World!!' in out
    assert bd.join('node_modules/jsmin/bin/jsmin').exists
    exit_code, proc_out = run('./wasp build', cwd=topdir.path)
    outs = proc_out.stdout.split('\n')
    assert '[SUCC]  Command: `configure`' in outs
    assert '[SUCC]  Command: `build`' in outs
    assert len(outs) == 2


def test_rustbuild():
    if not osinfo.linux or not check_exists():
        return
    topdir = directory(__file__).join('..').absolute
    directory(topdir.join('build')).remove()
    exit_code, proc_out = run('./wasp rust', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    err_lines = proc_out.stderr.split('\n')
    assert len(err_lines) == 1 and err_lines[0] == ''
    assert '[SUCC]  Command: `rust`' in out_lines
    assert any('rustc' in l for l in out_lines)
    exit_code, proc_out = run('./wasp rust', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert len(out_lines) == 2
    exit_code, proc_out = run('./wasp clean rust', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert any('rustc' in l for l in out_lines)
    assert '[SUCC]  Command: `rust`' in out_lines
    bd = directory(topdir.join('build'))
    main_file = bd.join('main').absolute
    assert main_file.exists
    exit_code, proc_out = run(main_file.path)
    out = proc_out.stdout.split('\n')
    assert 'Hello, World!' in out


def test_cppbuild():
    if not osinfo.linux or not check_exists():
        return


def test_qtbuild():
    if not osinfo.linux or not check_exists():
        return


if __name__ == '__main__':
    test_build()
    test_rustbuild()
