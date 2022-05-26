import datetime

import pytest

from databuilder.query_language import Dataset

from ..lib.mock_backend import EventLevelTable, PatientLevelTable
from . import tables


@pytest.fixture
def spec_test(request, engine):
    def run_test(table_data, series, expected_results, population=None):
        # Create SQLAlchemy model instances for each row of each table in table_data.
        input_data = []
        for table, s in table_data.items():
            model = {
                "patient_level_table": PatientLevelTable,
                "event_level_table": EventLevelTable,
            }[table.qm_node.name]
            input_data.extend(model(**row) for row in parse_table(s))

        # Populate database tables.
        engine.setup(*input_data)

        # To reduce noise in the tests we provide a default population which contains
        # all patients in tables p and e
        if population is None:
            population = tables.p.exists_for_patient() | tables.e.exists_for_patient()

        # Create a Dataset with the specified population and a single variable which is
        # the series under test.
        dataset = Dataset()
        dataset.set_population(population)
        dataset.v = series

        # Extract data, and check it's as expected.
        results = {r["patient_id"]: r["v"] for r in engine.extract(dataset)}
        assert results == expected_results

    return run_test


def parse_table(s):
    """Parse string containing table data, returning list of dicts.

    See test_conftest.py for examples.
    """

    header, _, *lines = s.strip().splitlines()
    col_names = [token.strip() for token in header.split("|")]
    col_names[0] = "PatientId"
    rows = [parse_row(col_names, line) for line in lines]
    return rows


def parse_row(col_names, line):
    """Parse string containing row data, returning list of values.

    See test_conftest.py for examples.
    """

    return {
        col_name: parse_value(col_name, token.strip())
        for col_name, token in zip(col_names, line.split("|"))
    }


def parse_value(col_name, value):
    """Parse string returning value of correct type for column.

    The desired type is determined by the name of the column.  An empty string indicates
    a null value.
    """

    if col_name == "PatientId" or col_name[0] == "i":
        parse = int
    elif col_name[0] == "b":
        parse = lambda v: {"T": True, "F": False}[v]  # noqa E731
    elif col_name[0] == "c":
        parse = str
    elif col_name[0] == "d":
        parse = datetime.date.fromisoformat
    else:
        assert False

    return parse(value) if value else None