import os


class Environment(dict):
    """
    Class representing the environment in which ``wasp`` runs in a dict like manner.
    It can be initialized from ``os.environ`` using :meth:`load_from_env`.
    The result can be obtained as an :class:`ArgumentCollection`
    using :meth:`argument_collection`.
    """
    def __init__(self):
        super().__init__()
        self.load_from_env()

    def load_from_env(self):
        """
        Loads this class from ``os.environ``
        """
        self.clear()
        self.update(dict(os.environ))

    def argument_collection(self):
        """
        Returns :class:`ArgumentCollection` object containing string
        arguments.
        """
        from . import ArgumentCollection, Argument
        ret = ArgumentCollection()
        for k, v in self.items():
            ret.add(Argument(k, value=v))
        return ret
