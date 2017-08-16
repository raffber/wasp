from wasp import node, ctx, FlagOption


class Latch(object):

    def __init__(self, on_option, off_option, description, default=True):
        self._on_option = str(on_option)
        self._off_option = str(off_option)
        self._description = str(description)
        self._key = self._on_option
        self._default = default

    @property
    def value(self):
        n = node(':latch/' + self._key)
        if ctx.options[self._on_option].value:
            n.write({
                'value': True
            })
        elif ctx.options[self._off_option].value:
            n.write({
                'value': False
            })
        return n.read().value('value', self._default)

    def options(self, opt):
        opt.add(FlagOption(self._on_option, 'Turn on ' + self._description))
        opt.add(FlagOption(self._off_option, 'Turn off ' + self._description))
