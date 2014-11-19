import os


class Environment(dict):
    def __init__(self):
        self.load_from_env()

    def load_from_env(self):
        self.clear()
        self.update(dict(os.environ))

    def argument_collection(self):
        raise NotImplementedError