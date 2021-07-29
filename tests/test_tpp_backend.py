from datetime import date, datetime

import pytest
from lib.tpp_schema import (
    Events,
    Patient,
    RegistrationHistory,
    SGSSNegativeTests,
    SGSSPositiveTests,
    apcs,
    organisation,
    patient,
    patient_address,
    registration,
)
from lib.util import extract

from cohortextractor import codelist, table
from cohortextractor.backends.tpp import TPPBackend


@pytest.mark.integration
def test_basic_events_and_registration(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1),
        Events(Patient_ID=1, CTV3Code="Code1"),
    )

    class Cohort:
        code = table("clinical_events").get("code")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, code="Code1")]


@pytest.mark.integration
def test_registration_dates(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2012-12-12"),
    )

    class Cohort:
        _registrations = table("practice_registrations")
        arrived = _registrations.get("date_start")
        left = _registrations.get("date_end")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, arrived=datetime(2001, 1, 1), left=datetime(2012, 12, 12))
    ]


@pytest.mark.integration
def test_covid_test_positive_result(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        SGSSPositiveTests(
            Patient_ID=1,
            Organism_Species_Name="SARS-CoV-2",
            Specimen_Date="2020-05-05",
        ),
    )

    class Cohort:
        date = (
            table("sgss_sars_cov_2").filter(positive_result=True).earliest().get("date")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


@pytest.mark.integration
def test_covid_test_negative_result(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
        SGSSNegativeTests(
            Patient_ID=1,
            Organism_Species_Name="SARS-CoV-2",
            Specimen_Date="2020-05-05",
        ),
    )

    class Cohort:
        date = (
            table("sgss_sars_cov_2")
            .filter(positive_result=False)
            .earliest()
            .get("date")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, date=date(2020, 5, 5))
    ]


@pytest.mark.integration
def test_patients_table(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1, Sex="F", DateOfBirth="1950-01-01"),
        RegistrationHistory(Patient_ID=1, StartDate="2001-01-01", EndDate="2026-06-26"),
    )

    class Cohort:
        _patients = table("patients")
        sex = _patients.get("sex")
        dob = _patients.get("date_of_birth")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, sex="F", dob=date(1950, 1, 1))
    ]


@pytest.mark.integration
def test_hospitalization_table_returns_admission_date(database, setup_tpp_database):
    setup_tpp_database(
        *patient(
            1,
            "M",
            registration("2001-01-01", "2026-06-26"),
            apcs(admission_date="2020-12-12"),
        )
    )

    class Cohort:
        admission = table("hospitalizations").get("date")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, admission=date(2020, 12, 12))
    ]


@pytest.mark.parametrize(
    "raw, codes",
    [
        ("flim", ["flim"]),
        ("flim ,flam ,flum", ["flim", "flam", "flum"]),
        ("flim ||flam ||flum", ["flim", "flam", "flum"]),
        ("abc ,def ||ghi ,jkl", ["abc", "def", "ghi", "jkl"]),
        ("ABCX ,XYZ ,OXO", ["ABC", "XYZ", "OXO"]),
    ],
    ids=[
        "returns a single code",
        "returns multiple space comma separated codes",
        "returns multiple space double pipe separated codes",
        "copes with comma pipe combinations",
        "strips just trailing xs",
    ],
)
@pytest.mark.integration
def test_hospitalization_table_code_conversion(
    database, setup_tpp_database, raw, codes
):
    setup_tpp_database(
        *patient(
            1,
            "M",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes=raw),
        )
    )

    class Cohort:
        code = table("hospitalizations").get("code")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, code=code) for code in codes
    ]


@pytest.mark.integration
def test_hospitalization_code_parsing_works_with_filters(database, setup_tpp_database):
    setup_tpp_database(
        *patient(
            1,
            "X",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes="abc"),
        ),
        *patient(
            2,
            "X",
            registration("2001-01-01", "2026-06-26"),
            apcs(codes="xyz"),
        ),
    )

    class Cohort:
        code = (
            table("hospitalizations")
            .filter("code", is_in=codelist(["xyz"], system="ctv3"))
            .get("code")
        )

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, code=None),
        dict(patient_id=2, code="xyz"),
    ]


@pytest.mark.integration
def test_events_with_numeric_value(database, setup_tpp_database):
    setup_tpp_database(
        Patient(Patient_ID=1),
        RegistrationHistory(Patient_ID=1),
        Events(Patient_ID=1, CTV3Code="Code1", NumericValue=34.7),
    )

    class Cohort:
        value = table("clinical_events").latest().get("numeric_value")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, value=34.7)]


@pytest.mark.integration
def test_organisation(database, setup_tpp_database):
    setup_tpp_database(
        organisation(1, "South"),
        organisation(2, "North"),
        *patient(1, "M", registration("2001-01-01", "2021-06-26", 1)),
        *patient(2, "F", registration("2001-01-01", "2026-06-26", 2)),
    )

    class Cohort:
        _registrations = table("practice_registrations").last_by("patient_id")
        region = _registrations.get("nuts1_region_name")
        practice_id = _registrations.get("pseudo_id")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, region="South", practice_id=1),
        dict(patient_id=2, region="North", practice_id=2),
    ]


@pytest.mark.integration
def test_organisation_dates(database, setup_tpp_database):
    setup_tpp_database(
        organisation(1, "South"),
        organisation(2, "North"),
        organisation(3, "West"),
        organisation(4, "East"),
        # registered at 2 practices, select the one active on 25/6
        *patient(
            1,
            "M",
            registration("2001-01-01", "2021-06-26", 1),
            registration("2021-06-27", "2026-06-26", 2),
        ),
        # registered at 2 practices with overlapping dates, select the latest
        *patient(
            2,
            "F",
            registration("2001-01-01", "2026-06-26", 2),
            registration("2021-01-01", "9999-12-31", 3),
        ),
        # registration not in range, not included
        *patient(3, "F", registration("2001-01-01", "2020-06-26", 2)),
    )

    class Cohort:
        _registrations = table("practice_registrations").date_in_range("2021-06-25")
        population = _registrations.exists()
        _registration_table = _registrations.latest("date_end")
        region = _registration_table.get("nuts1_region_name")
        practice_id = _registration_table.get("pseudo_id")

    assert extract(Cohort, TPPBackend, database) == [
        dict(patient_id=1, region="South", practice_id=1),
        dict(patient_id=2, region="West", practice_id=3),
    ]


@pytest.mark.integration
def test_index_of_multiple_deprivation(database, setup_tpp_database):
    setup_tpp_database(
        *patient(
            1,
            "M",
            registration("2001-01-01", "2026-06-26"),
            patient_address("2001-01-01", "2026-06-26", 1200, "E02000001"),
        )
    )

    class Cohort:
        imd = table("patient_address").imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, imd=1200)]


@pytest.mark.integration
@pytest.mark.parametrize(
    "patient_addresses,expected",
    [
        # two addresses recorded as current, choose the latest start date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 100, "E02000002"),
                patient_address("2021-01-01", "9999-12-31", 200, "E02000003"),
            ],
            200,
        ),
        # two addresses with same start, choose the latest end date
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "2021-01-01", 200, "E02000002"),
            ],
            300,
        ),
        # same dates, prefer the one with a postcode
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 400, "NPC"),
            ],
            300,
        ),
        # same dates and both have postcodes, select latest patientaddress id as tie-breaker
        (
            [
                patient_address("2001-01-01", "9999-12-31", 300, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 400, "E02000003"),
                patient_address("2001-01-01", "9999-12-31", 500, "E02000003"),
            ],
            500,
        ),
    ],
)
def test_index_of_multiple_deprivation_sorting(
    database, setup_tpp_database, patient_addresses, expected
):
    setup_tpp_database(
        *patient(1, "M", registration("2001-01-01", "2026-06-26"), *patient_addresses)
    )

    class Cohort:
        imd = table("patient_address").imd_rounded_as_of("2021-06-01")

    assert extract(Cohort, TPPBackend, database) == [dict(patient_id=1, imd=expected)]
