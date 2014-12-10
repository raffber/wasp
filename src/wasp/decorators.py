

class DecoratorStore(object):
    def __init__(self):
        self.init = []
        self.commands = []
        self.generators = []
        self.options = []
        self.create_context = None
        self.handle_options = []


decorators = DecoratorStore()