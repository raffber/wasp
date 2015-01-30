from wasp import shell, find_exe, File, group, ctx, Directory, files


RUST_BINARY_PATHS = ['/usr/bin', '/usr/local/bin']


def find_cargo(produce=True):
    t = find_exe('cargo', dirs=RUST_BINARY_PATHS, argprefix='cargo')
    if produce:
        t.produce(':rust/cargo')
    return t


def find_rustc(produce=True):
    t = find_exe('rustc', dirs=RUST_BINARY_PATHS, argprefix='rustc')
    if produce:
        t.produce(':rust/rustc')
    return t


def cargo_build(directory):
    if isinstance(directory, str):
        directory = Directory(directory)
    assert isinstance(directory, Directory), 'cargo_build() expects an argument of type str or Directory'
    return shell('{cargo} build', always=True, cwd=directory).use(':rust/cargo').require(('cargo', find_cargo))


def executable(source, target):
    target = ctx.builddir.join(target)
    return shell('{rustc} {SRC} -o {TGT}', sources=source, targets=target)\
        .use(':rust/rustc').require(('rustc', find_rustc))
