from wasp import *

class TouchTask(ShellTask):
    cmd = 'touch {TGT}'
    always = True

@configure
def configure():
    print('CONFIGURE!!!')
    return TouchTask(targets='asdf.txt')
 
