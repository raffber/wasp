from wasp import osinfo, directory
from wasp.shell import run


def check_exists():
    for exe in ['dmd', 'npm', 'rustc', 'cargo', 'gcc', 'moc']:
        if not directory('/usr/bin').join(exe).exists:
            return False
    return True


def test_cppbuild():
    if not osinfo.linux or not check_exists():
        return
    topdir = directory(__file__).join('..').absolute
    directory(topdir.join('build')).remove()
    exit_code, proc_out = run('./wasp cpp', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert '[SUCC]  Command: `cpp`' in out_lines
    exit_code, proc_out = run('./wasp cpp', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert len(out_lines) == 2
    assert '[SUCC]  Command: `cpp`' in out_lines
    bd = directory(topdir.join('build'))
    main_file = bd.join('main').absolute
    assert main_file.exists
    exit_code, proc_out = run(main_file.path)
    out = proc_out.stdout.split('\n')
    assert 'hello from cpp' in out


def test_qtbuild():
    if not osinfo.linux or not check_exists():
        return
    topdir = directory(__file__).join('..').absolute
    directory(topdir.join('build')).remove()
    exit_code, proc_out = run('./wasp qt', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert '[SUCC]  Command: `qt`' in out_lines
    exit_code, proc_out = run('./wasp qt', cwd=topdir.path)
    out_lines = proc_out.stdout.split('\n')
    assert len(out_lines) == 3
    assert '[SUCC]  Command: `qt`' in out_lines
    bd = directory(topdir.join('build'))
    main_file = bd.join('buildtest/qtmain').absolute
    assert main_file.exists
    exit_code, proc_out = run(main_file.path)
    out = proc_out.stdout.split('\n')
    assert 'hello from qt' in out


if __name__ == '__main__':
    test_cppbuild()
    test_qtbuild()
