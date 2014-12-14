from . import Serializable, factory


class Generator(Serializable):

    @property
    def key(self):
        pass

    def run(self):
        pass


class GeneratorCollection(dict, Serializable):

    def add(self, generator):
        self[generator.key] = generator

    @classmethod
    def from_json(cls, d):
        assert isinstance(d, dict), 'Expected dictionary of serialized generators.'
        return cls(factory.from_json(d))

    def to_json(self):
        d = super().to_json()
        d.update(dict((k, factory.to_json(v)) for k, v in self.items()))