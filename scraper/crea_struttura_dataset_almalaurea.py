from pathlib import Path

from utils import infer_survey_year, read_csv, write_ready_csvs


INPUT_CSV = None
DATA_DIR = Path("outputs/dati")
OUTPUT_DIR = Path("outputs/dati/ready")
READY_DEFINITION = "broad"

# Lascia None per usare l'anno presente nel master CSV.
SURVEY_YEAR = None


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


def run_crea_struttura_dataset_almalaurea(
    input_csv,
    data_dir,
    output_dir,
    ready_definition,
    survey_year,
):
    input_csv = input_csv if input_csv is not None else latest_master_csv(data_dir)
    rows = read_csv(input_csv)
    resolved_survey_year = survey_year if survey_year is not None else infer_survey_year(rows)

    write_ready_csvs(
        rows=rows,
        output_dir=output_dir,
        definition=ready_definition,
        survey_year=resolved_survey_year,
    )

    print(f"Read {len(rows)} rows from {input_csv}")
    print(f"Wrote ready-to-use CSVs to {output_dir}")


if __name__ == "__main__":
    run_crea_struttura_dataset_almalaurea(
        input_csv=INPUT_CSV,
        data_dir=DATA_DIR,
        output_dir=OUTPUT_DIR,
        ready_definition=READY_DEFINITION,
        survey_year=SURVEY_YEAR,
    )
