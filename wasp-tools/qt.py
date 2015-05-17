from wasp import nodes, shell, group, find_lib, find_exe, file, tool


_cpp = tool('cpp')


def find_moc(produce=True):
    t = find_exe('moc-qt5', argprefix='moc')
    if produce:
        t.produce(':qt/moc')
    return t



class Modules(object):
    core = 'Core'
    gui = 'Gui'



def find_modules(keys=[Modules.core, Modules.gui]):
    ret = []
    for key in keys:
        lowerkey = key.lower()
        # TODO: postprocess library names and remove 'lib' s.t. they can be linked with -l
        t = find_lib('libQt5'+key + '.so', dirs='/usr/lib', argprefix='libraries')
        t.produce(':qt/lib/' + lowerkey)
        ret.append(t)
    return group(ret)


def moc(fs):
    fs = nodes(fs)
    ret = []
    for f in fs:
        tgt = file(f).to_builddir().append_extension('moc')
        t = shell(cmd='{MOC} -o {TGT} {SRC}', sources=f.to_file(), targets=tgt)
        t.require('moc', spawn=find_moc)
        ret.append(t)
    return group(ret)


def program(fs):
    ret = []
    fs = nodes(fs)
    mocs = moc(fs)
    ret.append(mocs)
    fs.extend(mocs.targets)
    ret.append(compile(fs))


compile = _cpp.compile


def link(obj_files, target='main', use_default=True):
    t = _cpp.Link(sources=nodes(obj_files), targets=file(target).to_builddir())
    if use_default:
        ldnode = ':cpp/cxx'
        spawner = _cpp .find_cxx
        t.use(ldnode, libraries=['stdc++', 'c']).require('ld', spawn=spawner)
    return t
