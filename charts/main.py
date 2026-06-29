from pathlib import Path

from utils import (
    aggregate_filename,
    chart_filename,
    filter_dashboard_data,
    keep_total_rows,
    latest_dashboard_csv,
    load_dashboard_data,
    make_boxplot,
    make_scatterplot,
    source_year,
)


INPUT_CSV = None
DATA_DIR = Path("outputs/dati")
OUTPUT_DIR = Path("outputs/grafici")
AGGREGATE_OUTPUT_DIR = Path("outputs/dati/aggregati_grafici")

DEFINITION = "broad"

# Distanza temporale dalla laurea da visualizzare.
# Deve essere presente nel master CSV scaricato, per esempio [1, 3, 5].
YEARS_AFTER_DEGREE = [1, 5]

# Il batch replica le 4 strutture Tableau e crea varianti locali per i filtri scelti.
# Qui riproduciamo il filtro "tipo corso"; aggiungi atenei/gruppi solo quando servono davvero.
UNIVERSITY_FILTERS = ["*"]
DISCIPLINARY_GROUP_FILTERS = ["*"]
COURSE_TYPE_FILTERS = [
    "*",
    "laurea di primo livello",
    "laurea magistrale a ciclo unico",
    "laurea magistrale biennale",
]

# False significa: nei boxplot ogni punto e' un ateneo, non il totale nazionale.
INCLUDE_TOTAL_UNIVERSITY = False

MAKE_BOXPLOTS = True
MAKE_SCATTERS = True
SCATTER_SPLIT_DIMENSION = "disciplinary_group"
CLEAR_EXISTING_OUTPUTS = True


def clear_existing_outputs(output_dir, aggregate_output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("*.png"):
        path.unlink()
    for path in aggregate_output_dir.glob("*.csv"):
        path.unlink()


def run_charts(
    input_csv,
    output_dir,
    definition,
    years_after_degree,
    university_filters,
    disciplinary_group_filters,
    course_type_filters,
    include_total_university,
    make_boxplots,
    make_scatters,
    scatter_split_dimension,
    aggregate_output_dir,
    clear_existing_outputs_before_run,
):
    input_csv = input_csv if input_csv is not None else latest_dashboard_csv(DATA_DIR)
    data = load_dashboard_data(input_csv)
    survey_year = source_year(data)
    if clear_existing_outputs_before_run:
        clear_existing_outputs(output_dir, aggregate_output_dir)

    for years_value in years_after_degree:
        graduation_year = survey_year - years_value if survey_year else "unknown"
        for university in university_filters:
            for disciplinary_group in disciplinary_group_filters:
                for course_type in course_type_filters:
                    boxplot_filtered = filter_dashboard_data(
                        data=data,
                        years_after_degree=years_value,
                        definition=definition,
                        include_total_university=include_total_university,
                        include_total_course_type=True,
                        university=university,
                        disciplinary_group=disciplinary_group,
                        course_type=course_type,
                    )
                    boxplot_filtered = keep_total_rows(
                        boxplot_filtered,
                        course_type=course_type == "*",
                        degree_class=True,
                    )
                    scatter_filtered = filter_dashboard_data(
                        data=data,
                        years_after_degree=years_value,
                        definition=definition,
                        include_total_university=True,
                        include_total_course_type=True,
                        university=university,
                        disciplinary_group=disciplinary_group,
                        course_type=course_type,
                    )

                    if boxplot_filtered.empty and scatter_filtered.empty:
                        print(
                            "Skipped empty filter:",
                            f"annolau={years_value}",
                            f"ateneo={university}",
                            f"gruppo={disciplinary_group}",
                            f"tipo={course_type}",
                        )
                        continue

                    base_name = chart_filename(
                        "",
                        survey_year,
                        graduation_year,
                        years_value,
                        definition,
                        university,
                        disciplinary_group,
                        course_type,
                    ).strip("_")

                    if make_boxplots:
                        boxplot_path = output_dir / f"boxplot__{base_name}.png"
                        if boxplot_filtered.empty:
                            print(f"Skipped empty boxplot {boxplot_path}")
                        else:
                            try:
                                make_boxplot(
                                    boxplot_filtered,
                                    years_value,
                                    boxplot_path,
                                    university=university,
                                    disciplinary_group=disciplinary_group,
                                    course_type=course_type,
                                )
                                print(f"Wrote {boxplot_path}")
                            except ValueError as exc:
                                print(f"Skipped boxplot {boxplot_path}: {exc}")

                    if make_scatters:
                        scatter_base_name = f"{base_name}__split_{scatter_split_dimension}"
                        scatter_path = output_dir / f"scatter__{scatter_base_name}.png"
                        aggregate_path = aggregate_output_dir / aggregate_filename(
                            survey_year=survey_year,
                            graduation_year=graduation_year,
                            years_after_degree=years_value,
                            definition=definition,
                            filters=[
                                ("ateneo", university),
                                ("gruppo", disciplinary_group),
                                ("tipo", course_type),
                            ],
                            split_dimension=scatter_split_dimension,
                        )
                        if scatter_filtered.empty:
                            print(f"Skipped empty scatter {scatter_path}")
                        else:
                            try:
                                aggregate = make_scatterplot(
                                    scatter_filtered,
                                    years_value,
                                    scatter_path,
                                    university=university,
                                    disciplinary_group=disciplinary_group,
                                    course_type=course_type,
                                    split_dimension=scatter_split_dimension,
                                )
                                aggregate_path.parent.mkdir(parents=True, exist_ok=True)
                                aggregate.to_csv(aggregate_path, index=False, encoding="utf-8-sig")
                                print(f"Wrote {scatter_path}")
                                print(f"Wrote {aggregate_path}")
                            except ValueError as exc:
                                print(f"Skipped scatter {scatter_path}: {exc}")


if __name__ == "__main__":
    run_charts(
        input_csv=INPUT_CSV,
        output_dir=OUTPUT_DIR,
        definition=DEFINITION,
        years_after_degree=YEARS_AFTER_DEGREE,
        university_filters=UNIVERSITY_FILTERS,
        disciplinary_group_filters=DISCIPLINARY_GROUP_FILTERS,
        course_type_filters=COURSE_TYPE_FILTERS,
        include_total_university=INCLUDE_TOTAL_UNIVERSITY,
        make_boxplots=MAKE_BOXPLOTS,
        make_scatters=MAKE_SCATTERS,
        scatter_split_dimension=SCATTER_SPLIT_DIMENSION,
        aggregate_output_dir=AGGREGATE_OUTPUT_DIR,
        clear_existing_outputs_before_run=CLEAR_EXISTING_OUTPUTS,
    )
