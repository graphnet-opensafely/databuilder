import calendar
from pathlib import Path

import pytest
from codelists import (
    alt_codelist,
    asthma_codelist,
    cholesterol_codelist,
    copd_codelist,
    hba1c_codelist,
    medication_review_codelist,
    qrisk_codelist,
    rbc_codelist,
    sodium_codelist,
    systolic_bp_codelist,
    tsh_codelist,
)
from lib.tpp_schema import event, organisation, patient, registration
from lib.util import extract

from cohortextractor import Measure, cohort_date_range, table
from cohortextractor.backends import TPPBackend
from cohortextractor.main import get_measures
from cohortextractor.measure import MeasuresManager


index_date_range = cohort_date_range(
    start="2019-01-01", end="2019-02-10", increment="month"
)

measures_codelists = {
    "medication_review": medication_review_codelist,
    "systolic_bp": systolic_bp_codelist,
    "qrisk": qrisk_codelist,
    "cholesterol": cholesterol_codelist,
    "alt": alt_codelist,
    "tsh": tsh_codelist,
    "rbc": rbc_codelist,
    "hba1c": hba1c_codelist,
    "sodium": sodium_codelist,
    "asthma": asthma_codelist,
    "copd": copd_codelist,
}


def cohort(index_date):
    index_year, index_month, _ = index_date.split("-")
    last_day_of_index_month = calendar.monthrange(int(index_year), int(index_month))[1]
    end_of_index_month = f"{index_year}-{index_month}-{last_day_of_index_month}"

    class Cohort:
        # Population
        _registrations = table("practice_registrations").date_in_range(index_date)
        # There can be more than one registration per patient, get the latest one
        _latest_registrations = _registrations.latest("date_end")
        practice = _latest_registrations.get("pseudo_id")

        # TPP backend does not currently support deaths/death from any cause
        # _died = table("deaths").filter("date", on_or_before=index_date).exists()
        # population = _registrations.exists() & ~(_died.exists())
        population = _registrations.exists()

        # Add the codelist variables and measures
        measures = []

    for measure_name, target_codelist in measures_codelists.items():
        filtered_to_codelist = (
            table("clinical_events")
            .filter("code", is_in=target_codelist)
            .filter("date", between=[index_date, end_of_index_month])
        )
        variable_def = filtered_to_codelist.exists()
        setattr(Cohort, measure_name, variable_def)

        code_variable_def = filtered_to_codelist.latest().get("code")
        measure_event_code = f"{measure_name}_event_code"
        setattr(Cohort, measure_event_code, code_variable_def)

        Cohort.measures.extend(
            [
                Measure(
                    id=measure_name,
                    numerator=measure_name,
                    denominator="population",
                    group_by=["practice", measure_event_code],
                ),
                Measure(
                    id=f"{measure_name}_practice_only",
                    numerator=measure_name,
                    denominator="population",
                    group_by=["practice"],
                ),
            ]
        )
    return Cohort


@pytest.mark.integration
def test_cohort_tpp_backend(database, setup_backend_database):
    setup_backend_database(
        organisation(organisation_id=1, region="South"),
        organisation(organisation_id=2, region="North"),
        # present at index date 1
        *patient(
            1,
            "F",
            "1990-8-10",
            registration(
                start_date="2001-01-01", end_date="2019-01-10", organisation_id=1
            ),
            event(code="1079381000000109", date="2019-01-28"),  # medication review
            event(code="314440001", date="2019-01-28"),  # systolic_bp
            event(code="1085871000000105", date="2019-02-28"),  # qrisk, out of range
            event(code="389608004", date="2019-01-28"),  # cholesterol
            event(code="1013211000000103", date="2018-12-28"),  # alt, out of range
        ),
        # present at index date 2
        *patient(
            2,
            "M",
            "1990-1-1",
            registration(
                start_date="2019-01-15", end_date="2026-02-02", organisation_id=2
            ),
            event(code="1022791000000101", date="2019-01-28"),  # tsh, out of range
            event(code="365625004", date="2019-03-02"),  # rbc, out of range
            event(code="491841000000105", date="2019-02-28"),  # hba1c
            event(code="1000661000000107", date="2019-02-20"),  # sodium
            event(code="270442000", date="2019-02-13"),  # asthma
            event(code="394703002", date="2019-02-01"),  # copd
        ),
        # excluded by registration date
        *patient(
            3,
            "M",
            "1990-1-1",
            registration(
                start_date="2001-01-01", end_date="2002-02-02", organisation_id=1
            ),
            event(code="365625004", date="2019-03-02"),  # rbc
        ),
        backend="tpp",
    )

    run_sro_measures_test(database)


def run_sro_measures_test(database):
    expected = {
        1: dict(
            patient_id=1,
            practice=1,
            medication_review=True,
            medication_review_event_code="1079381000000109",
            systolic_bp=True,
            systolic_bp_event_code="314440001",
            qrisk=None,
            qrisk_event_code=None,
            cholesterol=True,
            cholesterol_event_code="389608004",
            alt=None,
            alt_event_code=None,
            tsh=None,
            tsh_event_code=None,
            rbc=None,
            rbc_event_code=None,
            hba1c=None,
            hba1c_event_code=None,
            sodium=None,
            sodium_event_code=None,
            asthma=None,
            asthma_event_code=None,
            copd=None,
            copd_event_code=None,
        ),
        2: dict(
            patient_id=2,
            practice=2,
            medication_review=None,
            medication_review_event_code=None,
            systolic_bp=None,
            systolic_bp_event_code=None,
            qrisk=None,
            qrisk_event_code=None,
            cholesterol=None,
            cholesterol_event_code=None,
            alt=None,
            alt_event_code=None,
            tsh=None,
            tsh_event_code=None,
            rbc=None,
            rbc_event_code=None,
            hba1c=True,
            hba1c_event_code="491841000000105",
            sodium=True,
            sodium_event_code="1000661000000107",
            asthma=True,
            asthma_event_code="270442000",
            copd=True,
            copd_event_code="394703002",
        ),
    }

    expected_measures = {
        1: {
            "medication_review": {"medication_review_event_code": "1079381000000109"},
            "medication_review_practice_only": {},
            "systolic_bp": {"systolic_bp_event_code": "314440001"},
            "systolic_bp_practice_only": {},
            "cholesterol": {"cholesterol_event_code": "389608004"},
            "cholesterol_practice_only": {},
        },
        2: {
            "hba1c": {"hba1c_event_code": "491841000000105"},
            "hba1c_practice_only": {},
            "sodium": {"sodium_event_code": "1000661000000107"},
            "sodium_practice_only": {},
            "asthma": {"asthma_event_code": "270442000"},
            "asthma_practice_only": {},
            "copd": {"copd_event_code": "394703002"},
            "copd_practice_only": {},
        },
    }

    for i, index_date in enumerate(index_date_range, start=1):
        cohort_cls = cohort(index_date)
        measures = get_measures(cohort_cls)
        data = extract(cohort_cls, TPPBackend, database)
        assert data == [expected[i]]
        measures_manager = MeasuresManager(measures, Path(""))
        measures_manager._load_patient_dataframe(data)
        measure_results = list(measures_manager.calculate_measures())

        assert len(measure_results) == len(measures_codelists) * 2
        for measure_id, measure_df in measure_results:
            if measure_id in expected_measures[i]:
                expected_measure_results = expected_measures[i].get(measure_id)
                measure_name = measure_id.replace("_practice_only", "")
                assert measure_df.loc[0].practice == i
                assert measure_df.loc[0].population == 1
                assert measure_df.loc[0][measure_name] == 1
                assert measure_df.loc[0].value == 1.0
                for column, value in expected_measure_results.items():
                    assert measure_df.loc[0][column] == value
            else:
                if measure_id.endswith("_practice_only"):
                    assert len(measure_df.columns) == 2
                    assert measure_df.loc[0].practice == i
                    assert measure_df.loc[0].population == 1
                else:
                    assert measure_df.empty