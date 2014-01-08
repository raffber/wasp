
class Option(object):
    pass


class FlagOption(object):
    pass


class EnableOption(object):
    pass


class StringOption(object):
    pass


class IntOption(object):
    pass


class OptionsCollection(object):
    def __init__(self, cachedir):
        pass

    def add_option(self, option):
        pass

    def add_enable_option(self):
        pass

    def add_string_option(self):
        pass

    def add_int_option(self):
        pass

    def add_flag_option(self):
        pass
