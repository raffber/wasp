from wasp import nodes, shell, group, find_lib, find_exe, file, tool


cpp = tool('cpp')


def find_moc():
    t = find_exe('moc', argprefix='moc')
    if produce:
        t.produce(':qt/moc')
    return t



class Components(object):
    core = 'Core'
    gui = 'Gui'



def find_libraries(keys = [Components.core, Components.gui]):
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
        t = shell(cmd='{MOC} -o {TGT} {SRC}', sources=f.to_file(), target=tgt)
        t.require(':qt/moc', spawn=find_moc)
        ret.append(t)
    return group(ret)


def program(fs):
    fs = nodes(fs)
    mocs = moc(fs)
    fs.extend(mocs.targets)
