from wasp import node, directory, tool, file, group, shell, ctx
from wasp import osinfo

cpp = tool('cpp')


def configure(capnp_builddir):
    ext = '.exe' if osinfo.windows else ''
    capnp_exec = capnp_builddir.join('bin/capnp' + ext)
    cpp_plugin = capnp_builddir.join('bin/capnpc-c++' + ext)
    java_plugin = capnp_builddir.join('bin/capnpc-java' + ext)
    capnp_include = capnp_builddir.join('include')
    node(':capnp/config').write({
        'capnp': file(capnp_exec),
        'cpp': cpp_plugin,
        'java': java_plugin,
        'includes': capnp_include,
        'capnp_include': capnp_include
    })


def compile(source_dir, langs=None):
    if langs is None:
        langs = ['cpp', 'java']
    schema_sources = []
    tasks = []
    source_dir = directory(source_dir)
    for src in source_dir.glob('.*\.capnp', recursive=False):
        for lang in langs:
            cmd = '{capnp} compile -I{capnp_include} --src-prefix={srcdir} -o{' + lang + '}:{outp} {src}'
            tgt = file(source_dir.to_builddir().join(src.basename)).append_extension('.c++')
            schema_sources.append(tgt)
            capnp = shell(cmd, sources=src, targets=tgt).require('capnp').use(':capnp/config')
            capnp.use(outp=ctx.builddir, srcdir=source_dir)
            tasks.append(capnp)
    schema_obj = cpp.compile(schema_sources).use(':capnp/config', includes=ctx.builddir)
    tasks.append(schema_obj)
    return group(tasks), schema_obj
