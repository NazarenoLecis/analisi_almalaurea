from pathlib import Path

from utils import (
    resolve_survey_year,
    scrape_dashboard_dataset_by_university,
    scrape_degree_class_dataset,
    scrape_degree_course_dataset,
    write_csv,
    write_lookup_csv,
)


SURVEY_YEAR = "latest"
# None scarica solo l'ultimo anno disponibile. Usa una lista, es. [2024, 2025, 2026],
# per rigenerare piu' anni nello stesso run.
SURVEY_YEARS = None
USE_LATEST_SURVEY_YEAR = True

# Distanze temporali AlmaLaurea necessarie alla dashboard.
YEARS_AFTER_DEGREE = [1, 3, 5]
DEFINITIONS = ["restrictive", "broad"]
WORKERS = 4
DEGREE_COURSE_WORKERS = 2

OUTPUT_DIR = Path("outputs/dati")
INCLUDE_DEGREE_CLASS_DATA = True
INCLUDE_DEGREE_COURSE_DATA = True
INCLUDE_TOTAL_GROUP = False

# Imposta numeri piccoli per test veloci, poi rimetti None per il download completo.
LIMIT_GROUPS = None
LIMIT_COURSE_TYPES = None


def data_filename(survey_year, years_after_degree, definitions):
    years_suffix = "_".join(str(value) for value in years_after_degree)
    definitions_suffix = "_".join(str(value) for value in definitions)
    return (
        f"almalaurea_occupazione__survey_{survey_year}"
        f"__annolau_{years_suffix}"
        f"__defs_{definitions_suffix}.csv"
    )


def sort_rows(rows):
    def as_sort_int(value):
        if value in {None, ""}:
            return -1
        return int(float(value))

    return sorted(
        rows,
        key=lambda row: (
            as_sort_int(row["survey_year"]),
            as_sort_int(row["years_after_degree"]),
            row["employment_definition"],
            str(row["disciplinary_group"]),
            str(row["course_type"]),
            str(row.get("degree_class", "*")),
            str(row.get("degree_course", "*")),
            str(row["university"]),
        ),
    )


def run_download_dati_almalaurea(
    survey_year,
    survey_years,
    use_latest_survey_year,
    years_after_degree,
    definitions,
    output_dir,
    workers,
    include_degree_class_data,
    include_degree_course_data,
    include_total_group,
    limit_groups,
    limit_course_types,
    degree_course_workers=None,
):
    requested_years = survey_years if survey_years is not None else [survey_year]
    resolved_survey_years = [
        resolve_survey_year(
            survey_year=year,
            use_latest_survey_year=use_latest_survey_year and survey_years is None,
        )
        for year in requested_years
    ]

    for resolved_survey_year in resolved_survey_years:
        run_download_dati_almalaurea_per_anno(
            resolved_survey_year=resolved_survey_year,
            years_after_degree=years_after_degree,
            definitions=definitions,
            output_dir=output_dir,
            workers=workers,
            include_degree_class_data=include_degree_class_data,
            include_degree_course_data=include_degree_course_data,
            include_total_group=include_total_group,
            limit_groups=limit_groups,
            limit_course_types=limit_course_types,
            degree_course_workers=degree_course_workers,
        )


def run_download_dati_almalaurea_per_anno(
    resolved_survey_year,
    years_after_degree,
    definitions,
    output_dir,
    workers,
    include_degree_class_data,
    include_degree_course_data,
    include_total_group,
    limit_groups,
    limit_course_types,
    degree_course_workers=None,
):
    rows, options = scrape_dashboard_dataset_by_university(
        survey_year=resolved_survey_year,
        years_after_degree_values=years_after_degree,
        definitions=definitions,
        include_total_group=include_total_group,
        limit_groups=limit_groups,
        limit_course_types=limit_course_types,
        workers=workers,
    )

    if include_degree_class_data:
        degree_class_rows, _ = scrape_degree_class_dataset(
            survey_year=resolved_survey_year,
            years_after_degree_values=years_after_degree,
            definitions=definitions,
            base_rows=rows,
            include_total_group=include_total_group,
            limit_groups=limit_groups,
            limit_course_types=limit_course_types,
            workers=workers,
        )
        rows.extend(degree_class_rows)

    if include_degree_course_data:
        degree_course_rows, _ = scrape_degree_course_dataset(
            survey_year=resolved_survey_year,
            years_after_degree_values=years_after_degree,
            definitions=definitions,
            base_rows=rows,
            include_total_group=include_total_group,
            limit_groups=limit_groups,
            limit_course_types=limit_course_types,
            workers=degree_course_workers or workers,
        )
        rows.extend(degree_course_rows)

    rows = sort_rows(rows)
    data_path = output_dir / data_filename(resolved_survey_year, years_after_degree, definitions)
    lookup_path = output_dir / f"almalaurea_lookups__survey_{resolved_survey_year}.csv"

    write_csv(data_path, rows)
    write_lookup_csv(lookup_path, options)

    print(f"Wrote {len(rows)} rows to {data_path}")
    print(f"Wrote lookup tables to {lookup_path}")


if __name__ == "__main__":
    run_download_dati_almalaurea(
        survey_year=SURVEY_YEAR,
        survey_years=SURVEY_YEARS,
        use_latest_survey_year=USE_LATEST_SURVEY_YEAR,
        years_after_degree=YEARS_AFTER_DEGREE,
        definitions=DEFINITIONS,
        output_dir=OUTPUT_DIR,
        workers=WORKERS,
        include_degree_class_data=INCLUDE_DEGREE_CLASS_DATA,
        include_degree_course_data=INCLUDE_DEGREE_COURSE_DATA,
        include_total_group=INCLUDE_TOTAL_GROUP,
        limit_groups=LIMIT_GROUPS,
        limit_course_types=LIMIT_COURSE_TYPES,
        degree_course_workers=DEGREE_COURSE_WORKERS,
    )
