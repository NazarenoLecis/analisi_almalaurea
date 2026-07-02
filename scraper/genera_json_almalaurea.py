from pathlib import Path

from crea_export_dashboard_almalaurea import (
    DASHBOARD_YEAR_WINDOW,
    DATA_OUTPUT,
    INPUT_CSV,
    INPUT_CSVS,
    METADATA_OUTPUT,
    OUTPUT_DIR as WEB_OUTPUT_DIR,
    TIMESERIES_INPUT_CSVS,
    TIMESERIES_OUTPUT,
    TIMESERIES_START_YEAR,
    run_crea_export_dashboard_almalaurea,
)
from download_dati_almalaurea import (
    DEFINITIONS,
    DEGREE_COURSE_WORKERS,
    INCLUDE_DEGREE_CLASS_DATA,
    INCLUDE_DEGREE_COURSE_DATA,
    INCLUDE_TOTAL_GROUP,
    LIMIT_COURSE_TYPES,
    LIMIT_GROUPS,
    OUTPUT_DIR as DATA_DIR,
    SURVEY_YEAR,
    USE_LATEST_SURVEY_YEAR,
    WORKERS,
    YEARS_AFTER_DEGREE,
    run_download_dati_almalaurea,
)
from utils import get_available_survey_years


# Configura qui il run, senza argomenti da terminale.
DOWNLOAD_DATA = True
EXPORT_JSON = True

# "all" scarica tutti gli anni pubblicati da AlmaLaurea.
# None scarica solo l'ultimo anno disponibile.
# Una lista scarica solo gli anni indicati, es. [2023, 2024, 2025].
SURVEY_YEARS_TO_DOWNLOAD = "all"
YEARS_AFTER_DEGREE_TO_DOWNLOAD = YEARS_AFTER_DEGREE

JSON_DASHBOARD_YEAR_WINDOW = DASHBOARD_YEAR_WINDOW
JSON_TIMESERIES_START_YEAR = TIMESERIES_START_YEAR


def normalized_survey_years(value):
    if value is None:
        return None
    if value == "all":
        return sorted(get_available_survey_years())
    return value


def print_json_outputs(output_dir):
    output_dir = Path(output_dir)
    print("JSON generati:")
    for filename in [DATA_OUTPUT, METADATA_OUTPUT, TIMESERIES_OUTPUT]:
        print(f"- {output_dir / filename}")


def run_genera_json_almalaurea():
    survey_years = normalized_survey_years(SURVEY_YEARS_TO_DOWNLOAD)

    if DOWNLOAD_DATA:
        run_download_dati_almalaurea(
            survey_year=SURVEY_YEAR,
            survey_years=survey_years,
            use_latest_survey_year=USE_LATEST_SURVEY_YEAR and survey_years is None,
            years_after_degree=YEARS_AFTER_DEGREE_TO_DOWNLOAD,
            definitions=DEFINITIONS,
            output_dir=DATA_DIR,
            workers=WORKERS,
            include_degree_class_data=INCLUDE_DEGREE_CLASS_DATA,
            include_degree_course_data=INCLUDE_DEGREE_COURSE_DATA,
            include_total_group=INCLUDE_TOTAL_GROUP,
            limit_groups=LIMIT_GROUPS,
            limit_course_types=LIMIT_COURSE_TYPES,
            degree_course_workers=DEGREE_COURSE_WORKERS,
        )

    if EXPORT_JSON:
        run_crea_export_dashboard_almalaurea(
            input_csv=INPUT_CSV,
            input_csvs=INPUT_CSVS,
            timeseries_input_csvs=TIMESERIES_INPUT_CSVS,
            data_dir=DATA_DIR,
            output_dir=WEB_OUTPUT_DIR,
            data_output=DATA_OUTPUT,
            metadata_output=METADATA_OUTPUT,
            timeseries_output=TIMESERIES_OUTPUT,
            dashboard_year_window=JSON_DASHBOARD_YEAR_WINDOW,
            timeseries_start_year=JSON_TIMESERIES_START_YEAR,
        )
        print_json_outputs(WEB_OUTPUT_DIR)


if __name__ == "__main__":
    run_genera_json_almalaurea()
