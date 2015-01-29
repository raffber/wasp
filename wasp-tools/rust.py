from wasp import shell, find_exe, File, group, ctx, Directory


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


def compile(sources, release=False):
    if isinstance(sources, str):
        sources = [sources]
    elif isinstance(sources, File):
        sources = [sources]
    tasks = []
    for s in sources:
        if isinstance(s, str):
            s = File(s)
        assert isinstance(s, File), 'rust.compile() expects a string or File or a list thereof'
        t = s.to_builddir().append_extension('.o')
        task = shell('{rustc} {SRC} -o {TGT}', sources=s, targets=t)\
            .use(':rust/rustc').require(('rustc', find_rustc))
        tasks.append(task)
    return group(tasks)


def link_executable(obj_files, name='main'):
    f = ctx.builddir.join(name)
    return shell('{rustc} {SRC} {TGT}', sources=obj_files, targets=f)\
        .use(':rust/rustc').require(('rustc', find_rustc))


def link_shlib(obj_files, name='main'):
    f = ctx.builddir.join(name)
    return shell('{rustc} {SRC} {TGT}', sources=obj_files, targets=f)\
        .use(':rust/rustc').require(('rustc', find_rustc))


def executable(sources, name='main', release=True):
    comp = compile(sources, release=release)
    link = link_executable(comp.targets, name=name)
    return group(comp, link)


def cargo_build(directory):
    if isinstance(directory, str):
        directory = Directory(directory)
    assert isinstance(directory, Directory), 'cargo_build() expects an argument of type str or Directory'
    return shell('{cargo} build', always=True, cwd=directory).use(':rust/cargo').require(('cargo', find_cargo))


def shlib(sources, name='main', release=True):
    comp = compile(sources, release=release)
    link = link_shlib(comp.targets, name=name)
    return group(comp, link)

