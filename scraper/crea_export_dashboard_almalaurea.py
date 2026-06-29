from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from utils import read_csv


INPUT_CSV = None
DATA_DIR = Path("outputs/dati")
OUTPUT_DIR = Path("outputs/web")
DATA_OUTPUT = "almalaurea_dashboard_data.json"
METADATA_OUTPUT = "almalaurea_metadata.json"


def latest_master_csv(data_dir):
    candidates = sorted(
        Path(data_dir).glob("almalaurea_occupazione__survey_*__annolau_*__defs_*.csv")
    )
    if not candidates:
        raise FileNotFoundError(f"No AlmaLaurea master CSV found in {data_dir}")
    return max(
        candidates,
        key=lambda path: int(path.name.split("__survey_")[1].split("__", 1)[0]),
    )


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
        for name in ["graduates", "employment_rate", "net_monthly_salary"]
    )


def dashboard_record(row):
    university = normalized_value(row.get("university"))
    group = normalized_value(row.get("disciplinary_group"))
    course_type = normalized_value(row.get("course_type"))
    degree_class = normalized_value(row.get("degree_class"))

    return {
        "survey_year": parse_int(row.get("survey_year")),
        "years_after_degree": parse_int(row.get("years_after_degree")),
        "graduation_year": parse_int(row.get("graduation_year")),
        "employment_definition": row.get("employment_definition"),
        "employment_definition_label": row.get("employment_definition_label"),
        "university": university,
        "university_label": display_value(university),
        "disciplinary_group": group,
        "disciplinary_group_label": display_value(group),
        "course_type": course_type,
        "course_type_label": display_value(course_type),
        "degree_class": degree_class,
        "degree_class_label": display_value(degree_class),
        "graduates": parse_int(row.get("graduates")),
        "employment_rate": parse_float(row.get("employment_rate")),
        "net_monthly_salary": parse_float(row.get("net_monthly_salary")),
        "is_university_total": university == "*",
        "is_degree_class_detail": degree_class != "*",
    }


def unique(records, field):
    return sort_values({record[field] for record in records if record.get(field) is not None})


def filter_options(records, field, label_field):
    values = {}
    for record in records:
        value = record.get(field)
        label = record.get(label_field)
        if value is not None and label is not None:
            values[value] = label
    return [
        {"value": value, "label": values[value]}
        for value in sort_values(values)
    ]


def build_metadata(records, source_path):
    survey_years = unique(records, "survey_year")
    graduation_years = unique(records, "graduation_year")
    years_after_degree = unique(records, "years_after_degree")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "AlmaLaurea - Condizione occupazionale dei laureati",
        "source_site": "https://www.almalaurea.it/",
        "source_csv": str(source_path).replace("\\", "/"),
        "latest_survey_year": survey_years[-1] if survey_years else None,
        "survey_years": survey_years,
        "graduation_years": graduation_years,
        "years_after_degree": years_after_degree,
        "record_count": len(records),
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
            "university": filter_options(records, "university", "university_label"),
            "disciplinary_group": filter_options(
                records,
                "disciplinary_group",
                "disciplinary_group_label",
            ),
            "course_type": filter_options(records, "course_type", "course_type_label"),
            "degree_class": filter_options(records, "degree_class", "degree_class_label"),
        },
        "methodology": [
            "La coorte di laurea e' calcolata come anno indagine meno anni dalla laurea.",
            "Non tutte le combinazioni di filtri sono pubblicate da AlmaLaurea.",
            "I valori mancanti dipendono dalla disponibilita' delle viste sul sito sorgente.",
            "La retribuzione e' espressa come retribuzione mensile netta.",
        ],
    }


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))


def run_crea_export_dashboard_almalaurea(
    input_csv,
    data_dir,
    output_dir,
    data_output,
    metadata_output,
):
    input_csv = input_csv if input_csv is not None else latest_master_csv(data_dir)
    rows = read_csv(input_csv)
    records = [
        dashboard_record(row)
        for row in rows
        if row_has_metrics(row)
    ]
    metadata = build_metadata(records, input_csv)

    write_json(Path(output_dir) / data_output, {"metadata": metadata, "records": records})
    write_json(Path(output_dir) / metadata_output, metadata)

    print(f"Read {len(rows)} rows from {input_csv}")
    print(f"Wrote {len(records)} dashboard records to {Path(output_dir) / data_output}")
    print(f"Wrote metadata to {Path(output_dir) / metadata_output}")


if __name__ == "__main__":
    run_crea_export_dashboard_almalaurea(
        input_csv=INPUT_CSV,
        data_dir=DATA_DIR,
        output_dir=OUTPUT_DIR,
        data_output=DATA_OUTPUT,
        metadata_output=METADATA_OUTPUT,
    )
