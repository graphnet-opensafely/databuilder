import csv
import importlib
import inspect
import os
import sys
import time
from pathlib import Path

import sqlalchemy
import sqlalchemy.exc

from .query_utils import get_column_definitions


def main(workspace="/workspace", db_url=None):
    if not db_url:
        db_url = os.environ["TPP_DATABASE_URL"]
    url = sqlalchemy.engine.make_url(db_url)
    assert url.drivername == "mssql"
    url = url.set(drivername="mssql+pymssql")
    engine = sqlalchemy.create_engine(url, echo=True, future=True)

    timeout = 20
    limit = time.time() + timeout
    up = False
    while not up:
        try:
            with engine.connect() as conn:
                result = conn.execute(sqlalchemy.text("select 'hello world'"))
                assert result.first() == ("hello world",)
                up = True
        except sqlalchemy.exc.OperationalError as e:
            if time.time() >= limit:
                raise Exception(
                    f"Failed to connect to mssql after {timeout} seconds"
                ) from e
            time.sleep(1)

    sys.path.append(workspace)
    study_definition = importlib.import_module("study_definition")

    cohort_classes = [
        obj
        for name, obj in inspect.getmembers(study_definition)
        if inspect.isclass(obj)
    ]
    assert len(cohort_classes) == 1, "A study definition must contain one class only"
    Cohort = cohort_classes[0]

    cohort = get_column_definitions(Cohort)

    # We always want to include the patient id.
    columns = [("patient_id", "patient_id")]

    table_name = None

    for dst_column, query in cohort.items():
        # For now, we only support querying a single table.
        if not table_name:
            table_name = query.source.name
        else:
            assert table_name == query.source.name
        columns.append((query.column, dst_column))

    metadata = sqlalchemy.MetaData()
    table = sqlalchemy.Table(table_name, metadata, autoload_with=engine)

    # Turn each source/destination pair into a SQL "AS" clause.
    query = sqlalchemy.select(*[table.c[src].label(dst) for src, dst in columns])

    with engine.connect() as conn:
        results = conn.execute(query)

        path = Path(workspace) / "outputs/cohort.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode="w") as f:
            writer = csv.writer(f)
            writer.writerow(dst for _, dst in columns)

            for row in results:
                writer.writerow(row)
