import databuilder.main
from databuilder import table


def extract(cohort, backend, database, **backend_kwargs):
    return list(
        databuilder.main.extract(cohort, backend(database.host_url(), **backend_kwargs))
    )


class RecordingReporter:
    def __init__(self):
        self.msg = ""

    def __call__(self, msg):
        self.msg = msg


def null_reporter(msg):
    pass


def iter_flatten(iterable, iter_classes=(list, tuple)):
    """
    Iterate over `iterable` recursively flattening any lists or tuples
    encountered
    """
    for item in iterable:
        if isinstance(item, iter_classes):
            yield from iter_flatten(item, iter_classes)
        else:
            yield item


class OldCohortWithPopulation:
    def __init_subclass__(cls):
        if not hasattr(cls, "population"):  # pragma: no cover
            cls.population = table("practice_registrations").exists()
