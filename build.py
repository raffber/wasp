from wasp import *

@create_context
def init_hook():
    print('create context')
    return Context(awesome-test)
