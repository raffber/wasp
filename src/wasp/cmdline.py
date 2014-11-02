from .decorators import decorators


class postprocess_options(object):
    def __init__(self, f):
        decorators.postprocess_options.append(f)