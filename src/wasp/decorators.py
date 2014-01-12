class DecoratorStore(object):
    def __init__(self):
        self.init = []
        self.commands = []
        self.generators = []
        self.configure_options = []
        self.options = []


decorators = DecoratorStore()