from pathlib import Path

from download_dati_almalaurea import DEFINITIONS, OUTPUT_DIR, sort_rows
from utils import (
    infer_survey_year,
    read_csv,
    scrape_degree_course_dataset,
    write_csv,
)


INPUT_CSV = OUTPUT_DIR / "almalaurea_occupazione__survey_2025__annolau_1_5__defs_restrictive_broad.csv"
YEARS_AFTER_DEGREE = [1, 5]
WORKERS = 2


def base_rows_for_degree_courses(rows):
    return [
        row
        for row in rows
        if row.get("degree_class", "*") == "*"
        and row.get("degree_course", "*") in {"", "*"}
    ]


def run_recupera_corsi_almalaurea(input_csv, years_after_degree, definitions, workers):
    input_csv = Path(input_csv)
    rows = read_csv(input_csv)
    survey_year = infer_survey_year(rows)
    base_rows = base_rows_for_degree_courses(rows)
    print(f"Base rows for degree-course recovery: {len(base_rows)}")

    degree_course_rows, _ = scrape_degree_course_dataset(
        survey_year=survey_year,
        years_after_degree_values=years_after_degree,
        definitions=definitions,
        base_rows=base_rows,
        workers=workers,
    )
    print(f"Recovered degree-course rows: {len(degree_course_rows)}")

    rows = [
        row
        for row in rows
        if row.get("degree_course", "*") in {"", "*"}
    ]
    rows.extend(degree_course_rows)
    rows = sort_rows(rows)
    write_csv(input_csv, rows)
    print(f"Wrote {len(rows)} rows to {input_csv}")


if __name__ == "__main__":
    run_recupera_corsi_almalaurea(
        input_csv=INPUT_CSV,
        years_after_degree=YEARS_AFTER_DEGREE,
        definitions=DEFINITIONS,
        workers=WORKERS,
    )
