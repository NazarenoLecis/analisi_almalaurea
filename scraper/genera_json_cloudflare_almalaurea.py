from __future__ import annotations

import argparse
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


def parse_int_list(value):
    return [
        int(item.strip())
        for item in str(value).split(",")
        if item.strip()
    ]


def expand_year_token(token):
    token = token.strip().lower()
    if token in {"latest", "ultimo"}:
        return ["latest"]
    if "-" in token:
        start, end = token.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(token)]


def parse_survey_years(value):
    value = str(value).strip().lower()
    if value in {"latest", "ultimo"}:
        return None
    if value == "all":
        return sorted(get_available_survey_years())

    years = []
    for token in value.split(","):
        years.extend(expand_year_token(token))
    return years


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Scarica i dati AlmaLaurea necessari alla dashboard e rigenera "
            "i JSON statici da pubblicare su Cloudflare."
        )
    )
    parser.add_argument(
        "--survey-years",
        default="latest",
        help=(
            "'latest' per l'ultimo anno disponibile, 'all' per tutti gli anni "
            "AlmaLaurea, oppure una lista/range tipo '2024,2025,2026' o '2008-2026'."
        ),
    )
    parser.add_argument(
        "--years-after-degree",
        default=",".join(str(value) for value in YEARS_AFTER_DEGREE),
        help="Distanze dalla laurea da scaricare, default: 1,3,5.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Rigenera solo i JSON usando i CSV gia' presenti in outputs/dati.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Scarica solo i CSV senza rigenerare i JSON.",
    )
    parser.add_argument(
        "--dashboard-year-window",
        type=int,
        default=DASHBOARD_YEAR_WINDOW,
        help="Numero di anni recenti da includere nel JSON dettagliato.",
    )
    parser.add_argument(
        "--timeseries-start-year",
        type=int,
        default=TIMESERIES_START_YEAR,
        help="Primo anno da includere nel JSON delle serie storiche.",
    )
    return parser


def print_cloudflare_outputs(output_dir):
    output_dir = Path(output_dir)
    print("JSON pronti per Cloudflare:")
    for filename in [DATA_OUTPUT, METADATA_OUTPUT, TIMESERIES_OUTPUT]:
        print(f"- {output_dir / filename}")


def main():
    args = build_parser().parse_args()
    survey_years = parse_survey_years(args.survey_years)
    years_after_degree = parse_int_list(args.years_after_degree)

    if not args.skip_download:
        run_download_dati_almalaurea(
            survey_year=SURVEY_YEAR,
            survey_years=survey_years,
            use_latest_survey_year=USE_LATEST_SURVEY_YEAR and survey_years is None,
            years_after_degree=years_after_degree,
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

    if not args.skip_export:
        run_crea_export_dashboard_almalaurea(
            input_csv=INPUT_CSV,
            input_csvs=INPUT_CSVS,
            timeseries_input_csvs=TIMESERIES_INPUT_CSVS,
            data_dir=DATA_DIR,
            output_dir=WEB_OUTPUT_DIR,
            data_output=DATA_OUTPUT,
            metadata_output=METADATA_OUTPUT,
            timeseries_output=TIMESERIES_OUTPUT,
            dashboard_year_window=args.dashboard_year_window,
            timeseries_start_year=args.timeseries_start_year,
        )
        print_cloudflare_outputs(WEB_OUTPUT_DIR)


if __name__ == "__main__":
    main()
