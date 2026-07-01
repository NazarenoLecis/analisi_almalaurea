from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils import read_csv


INPUT_CSV = None
INPUT_CSVS = None
TIMESERIES_INPUT_CSVS = None
DATA_DIR = Path("outputs/dati")
OUTPUT_DIR = Path("outputs/web")
DATA_OUTPUT = "almalaurea_dashboard_data.json"
METADATA_OUTPUT = "almalaurea_metadata.json"
TIMESERIES_OUTPUT = "almalaurea_timeseries_data.json"
DASHBOARD_YEAR_WINDOW = 10
TIMESERIES_START_YEAR = 2008


def latest_master_csv(data_dir):
    candidates = master_csvs(data_dir)
    if not candidates:
        raise FileNotFoundError(f"No AlmaLaurea master CSV found in {data_dir}")
    return max(
        candidates,
        key=lambda path: int(path.name.split("__survey_")[1].split("__", 1)[0]),
    )


def survey_year_from_path(path):
    return int(Path(path).name.split("__survey_")[1].split("__", 1)[0])


def years_after_degree_from_path(path):
    suffix = Path(path).name.split("__annolau_", 1)[1].split("__defs_", 1)[0]
    return tuple(int(value) for value in suffix.split("_") if value.isdigit())


def master_csv_priority(path):
    years_after_degree = years_after_degree_from_path(path)
    return (
        len(set(years_after_degree)),
        years_after_degree,
        Path(path).stat().st_mtime,
    )


def select_recent_paths(paths, year_window):
    paths = list(paths)
    if year_window is None:
        return paths
    years = sorted({survey_year_from_path(path) for path in paths})
    selected_years = set(years[-year_window:])
    return [
        path
        for path in paths
        if survey_year_from_path(path) in selected_years
    ]


def select_paths_from_year(paths, start_year):
    paths = list(paths)
    if start_year is None:
        return paths
    return [
        path
        for path in paths
        if survey_year_from_path(path) >= int(start_year)
    ]


def dashboard_csvs(input_csv, input_csvs, data_dir, dashboard_year_window):
    if input_csvs is not None:
        return [Path(path) for path in input_csvs]
    if input_csv is not None:
        return [Path(input_csv)]
    return select_recent_paths(master_csvs(data_dir), dashboard_year_window)


def timeseries_csvs(timeseries_input_csvs, data_dir, timeseries_start_year):
    if timeseries_input_csvs is not None:
        return [Path(path) for path in timeseries_input_csvs]
    return select_paths_from_year(master_csvs(data_dir), timeseries_start_year)


def master_csvs(data_dir):
    candidates = sorted(
        Path(data_dir).glob("almalaurea_occupazione__survey_*__annolau_*__defs_*.csv")
    )
    preferred_by_year = {}
    for path in candidates:
        survey_year = survey_year_from_path(path)
        current = preferred_by_year.get(survey_year)
        if current is None or master_csv_priority(path) > master_csv_priority(current):
            preferred_by_year[survey_year] = path
    return [
        preferred_by_year[survey_year]
        for survey_year in sorted(preferred_by_year)
    ]


def parse_int(value):
    if value in {None, ""}:
        return None
    return int(float(value))


def parse_float(value):
    if value in {None, ""}:
        return None
    return float(value)


def normalized_value(value):
    return "*" if value in {None, ""} else str(value)


def display_value(value, total_label="Totale"):
    value = normalized_value(value)
    return total_label if value == "*" else value


def sort_values(values):
    return sorted(values, key=lambda value: (value == "*", str(value).lower()))


def row_has_metrics(row):
    return any(
        row.get(name) not in {None, ""}
        for name in [
            "graduates",
            "employment_rate",
            "net_monthly_salary",
            "second_level_enrollment_rate",
        ]
    )


def dashboard_record(row):
    university = normalized_value(row.get("university"))
    group = normalized_value(row.get("disciplinary_group"))
    course_type = normalized_value(row.get("course_type"))
    degree_class = normalized_value(row.get("degree_class"))
    degree_course = normalized_value(row.get("degree_course"))

    return {
        "survey_year": parse_int(row.get("survey_year")),
        "years_after_degree": parse_int(row.get("years_after_degree")),
        "graduation_year": parse_int(row.get("graduation_year")),
        "employment_definition": row.get("employment_definition"),
        "university": university,
        "disciplinary_group": group,
        "course_type": course_type,
        "degree_class": degree_class,
        "degree_course": degree_course,
        "graduates": parse_int(row.get("graduates")),
        "employment_rate": parse_float(row.get("employment_rate")),
        "net_monthly_salary": parse_float(row.get("net_monthly_salary")),
        "second_level_enrollment_rate": parse_float(row.get("second_level_enrollment_rate")),
    }


def timeseries_record(row):
    university = normalized_value(row.get("university"))
    group = normalized_value(row.get("disciplinary_group"))
    course_type = normalized_value(row.get("course_type"))
    degree_class = normalized_value(row.get("degree_class"))
    degree_course = normalized_value(row.get("degree_course"))
    if degree_class != "*" or degree_course != "*":
        return None

    return {
        "survey_year": parse_int(row.get("survey_year")),
        "years_after_degree": parse_int(row.get("years_after_degree")),
        "graduation_year": parse_int(row.get("graduation_year")),
        "employment_definition": row.get("employment_definition"),
        "university": university,
        "disciplinary_group": group,
        "course_type": course_type,
        "graduates": parse_int(row.get("graduates")),
        "employment_rate": parse_float(row.get("employment_rate")),
        "net_monthly_salary": parse_float(row.get("net_monthly_salary")),
        "second_level_enrollment_rate": parse_float(row.get("second_level_enrollment_rate")),
    }


def unique(records, field):
    return sort_values({record[field] for record in records if record.get(field) is not None})


def filter_options(records, field, include_wildcard=False):
    values = {}
    if include_wildcard:
        values["*"] = "Totale"
    for record in records:
        value = record.get(field)
        if value is not None:
            values[value] = display_value(value)
    ordered_values = sort_values(values)
    if include_wildcard and "*" in values:
        ordered_values = ["*"] + [
            value
            for value in ordered_values
            if value != "*"
        ]
    return [
        {"value": value, "label": values[value]}
        for value in ordered_values
    ]


def build_metadata(records, source_paths, timeseries_records=None, timeseries_paths=None):
    survey_years = unique(records, "survey_year")
    graduation_years = unique(records, "graduation_year")
    years_after_degree = unique(records, "years_after_degree")
    timeseries_records = timeseries_records or []
    timeseries_years = unique(timeseries_records, "survey_year")
    source_paths = [Path(path) for path in source_paths]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "AlmaLaurea - Condizione occupazionale dei laureati",
        "source_site": "https://www.almalaurea.it/",
        "source_csv": str(source_paths[-1]).replace("\\", "/") if source_paths else None,
        "source_csvs": [
            str(path).replace("\\", "/")
            for path in source_paths
        ],
        "timeseries_csvs": [
            str(path).replace("\\", "/")
            for path in (timeseries_paths or [])
        ],
        "latest_survey_year": survey_years[-1] if survey_years else None,
        "survey_years": survey_years,
        "timeseries_years": timeseries_years,
        "dashboard_year_window": len(survey_years),
        "timeseries_start_year": timeseries_years[0] if timeseries_years else None,
        "graduation_years": graduation_years,
        "years_after_degree": years_after_degree,
        "record_count": len(records),
        "timeseries_record_count": len(timeseries_records),
        "definitions": [
            {
                "value": "broad",
                "label": "Occupati incl. formazione retribuita",
                "description": (
                    "Definizione meno restrittiva: include anche chi svolge "
                    "attivita' di formazione retribuita."
                ),
            },
            {
                "value": "restrictive",
                "label": "Occupati escl. formazione retribuita",
                "description": (
                    "Definizione restrittiva: esclude chi svolge attivita' "
                    "di formazione retribuita."
                ),
            },
        ],
        "metrics": [
            {
                "value": "employment_rate",
                "label": "Tasso di occupazione",
                "unit": "%",
            },
            {
                "value": "net_monthly_salary",
                "label": "Retribuzione mensile netta",
                "unit": "euro",
            },
            {
                "value": "second_level_enrollment_rate",
                "label": "Iscritti a magistrale",
                "unit": "%",
                "description": (
                    "Quota disponibile per le lauree di primo livello: aiuta a "
                    "interpretare il tasso di occupazione quando molti laureati "
                    "proseguono gli studi."
                ),
            },
        ],
        "filters": {
            "survey_year": [{"value": value, "label": str(value)} for value in survey_years],
            "graduation_year": [{"value": value, "label": str(value)} for value in graduation_years],
            "years_after_degree": [
                {
                    "value": value,
                    "label": f"{value} anno" if value == 1 else f"{value} anni",
                }
                for value in years_after_degree
            ],
            "employment_definition": [
                {"value": "broad", "label": "Incl. formazione retribuita"},
                {"value": "restrictive", "label": "Escl. formazione retribuita"},
            ],
            "university": filter_options(records, "university", include_wildcard=True),
            "disciplinary_group": filter_options(
                records,
                "disciplinary_group",
                include_wildcard=True,
            ),
            "course_type": filter_options(records, "course_type", include_wildcard=True),
            "degree_class": filter_options(records, "degree_class", include_wildcard=True),
            "degree_course": filter_options(records, "degree_course", include_wildcard=True),
        },
        "methodology": [
            "La coorte di laurea e' calcolata come anno indagine meno anni dalla laurea.",
            "La dashboard dettagliata carica gli ultimi 10 anni di indagine disponibili.",
            "Le serie storiche usano dati aggregati, senza dettaglio per classe di laurea, dal primo anno storico scaricato.",
            "Per le lauree di primo livello e' disponibile anche la quota di laureati iscritti a un corso di secondo livello.",
            "Nelle serie storiche, a parita' di anni dalla laurea, ogni anno di indagine osserva una coorte diversa.",
            "Non tutte le combinazioni di filtri sono pubblicate da AlmaLaurea.",
            "I tipi di corso possono cambiare nel tempo; le serie mostrano solo le combinazioni disponibili in ciascun anno.",
            "Il dettaglio per corso di laurea usa la variabile postcorso pubblicata da AlmaLaurea quando e' disponibile.",
            "I valori mancanti dipendono dalla disponibilita' delle viste sul sito sorgente.",
            "La retribuzione e' espressa come retribuzione mensile netta.",
        ],
    }


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))


def read_dashboard_records(path):
    rows = read_csv(path)
    records = [
        dashboard_record(row)
        for row in rows
        if row_has_metrics(row)
    ]
    return rows, records


def read_dashboard_records_from_paths(paths):
    rows = []
    records = []
    for path in paths:
        path_rows, path_records = read_dashboard_records(path)
        rows.extend(path_rows)
        records.extend(path_records)
    return rows, records


def read_timeseries_records(paths):
    records = []
    for path in paths:
        for row in read_csv(path):
            if not row_has_metrics(row):
                continue
            record = timeseries_record(row)
            if record is not None:
                records.append(record)
    return records


def run_crea_export_dashboard_almalaurea(
    input_csv,
    input_csvs,
    timeseries_input_csvs,
    data_dir,
    output_dir,
    data_output,
    metadata_output,
    timeseries_output,
    dashboard_year_window,
    timeseries_start_year,
):
    input_paths = dashboard_csvs(
        input_csv=input_csv,
        input_csvs=input_csvs,
        data_dir=data_dir,
        dashboard_year_window=dashboard_year_window,
    )
    timeseries_paths = timeseries_csvs(
        timeseries_input_csvs=timeseries_input_csvs,
        data_dir=data_dir,
        timeseries_start_year=timeseries_start_year,
    )

    rows, records = read_dashboard_records_from_paths(input_paths)
    timeseries_records = read_timeseries_records(timeseries_paths)
    metadata = build_metadata(
        records=records,
        source_paths=input_paths,
        timeseries_records=timeseries_records,
        timeseries_paths=timeseries_paths,
    )

    write_json(Path(output_dir) / data_output, {"metadata": metadata, "records": records})
    write_json(Path(output_dir) / metadata_output, metadata)
    write_json(
        Path(output_dir) / timeseries_output,
        {"metadata": metadata, "records": timeseries_records},
    )

    print(f"Read {len(rows)} rows from {len(input_paths)} input CSV files")
    print(f"Wrote {len(records)} dashboard records to {Path(output_dir) / data_output}")
    print(
        f"Wrote {len(timeseries_records)} time-series records "
        f"to {Path(output_dir) / timeseries_output}"
    )
    print(f"Wrote metadata to {Path(output_dir) / metadata_output}")


if __name__ == "__main__":
    run_crea_export_dashboard_almalaurea(
        input_csv=INPUT_CSV,
        input_csvs=INPUT_CSVS,
        timeseries_input_csvs=TIMESERIES_INPUT_CSVS,
        data_dir=DATA_DIR,
        output_dir=OUTPUT_DIR,
        data_output=DATA_OUTPUT,
        metadata_output=METADATA_OUTPUT,
        timeseries_output=TIMESERIES_OUTPUT,
        dashboard_year_window=DASHBOARD_YEAR_WINDOW,
        timeseries_start_year=TIMESERIES_START_YEAR,
    )
