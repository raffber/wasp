from wasp import shell, find_exe, ctx, Directory, spawn

RUST_BINARY_PATHS = ['/usr/bin', '/usr/local/bin']


def find_cargo(use_default=True):
    t = find_exe('cargo', dirs=RUST_BINARY_PATHS, argprefix='cargo')
    if use_default:
        t.produce(':rust/cargo')
    return t


def find_rustc(use_default=True):
    t = find_exe('rustc', dirs=RUST_BINARY_PATHS, argprefix='rustc')
    if use_default:
        t.produce(':rust/rustc')
    return t


def cargo_build(directory, use_default=True):
    if isinstance(directory, str):
        directory = Directory(directory)
    assert isinstance(directory, Directory), 'cargo_build() expects an argument of type str or Directory'
    t = shell('{cargo} build', always=True, cwd=directory).require('cargo')
    if use_default:
        t.use(spawn(':rust/cargo', find_cargo))
    return t


def executable(source, target, use_default=True):
    target = ctx.builddir.join(target)
    t = shell('{rustc} {src} -o {tgt}', sources=source, targets=target).require('rustc')
    if use_default:
        t.use(spawn(':rust/rustc', find_rustc))
    return t
