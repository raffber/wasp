from . import Serializable, factory


class Generator(Serializable):

    @property
    def key(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError


class GeneratorCollection(dict, Serializable):

    def add(self, generator):
        self[generator.key] = generator

    @classmethod
    def from_json(cls, d):
        assert isinstance(d, dict), 'Expected dictionary of serialized generators.'
        ret = {}
        for key, value in d.items():
            if key == '__type__':
                continue
            ret[key] = factory.from_json(value)
        return cls(ret)

    def to_json(self):
        d = super().to_json()
        for k, v in self.items():
            d[k] = v.to_json()
        return d


factory.register(GeneratorCollection)