from __future__ import annotations

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


BASE_URL = "https://www2.almalaurea.it/cgi-php/universita/statistiche"
USER_AGENT = "analisi-almalaurea/0.1"

DEFAULT_VISUALIZZA_PARAMS = {
    "CONFIG": "occupazione",
    "area4": "tutti",
    "classe": "tutti",
    "condocc": "tutti",
    "corstipo": "tutti",
    "facolta": "tutti",
    "iscrls": "tutti",
    "isstella": "0",
    "livello": "tutti",
    "pa": "tutti",
    "postcorso": "tutti",
}

DEFINITION_BY_SECTION = {
    4: "restrictive",
    8: "restrictive",
    104: "broad",
    108: "broad",
}

DEFINITION_LABELS = {
    "restrictive": "occupato_definizione_restrittiva",
    "broad": "occupato_definizione_meno_restrittiva",
}

COURSE_TYPE_CODES = {
    "*": "tutti",
    "laurea di primo livello": "L",
    "laurea magistrale a ciclo unico": "LSE",
    "laurea magistrale biennale": "LS",
}

OUTPUT_COLUMNS = [
    "survey_year",
    "years_after_degree",
    "graduation_year",
    "employment_definition",
    "employment_definition_label",
    "university_code",
    "university",
    "disciplinary_group_code",
    "disciplinary_group",
    "course_type_code",
    "course_type",
    "degree_class_code",
    "degree_class",
    "graduates",
    "employment_rate",
    "net_monthly_salary",
    "source_url",
]

READY_BOXPLOT_COLUMNS = [
    "Color_field",
    "Retribuzione mensile netta",
    "Ateneo",
    "Gruppo disciplinare",
    "Tipo di corso",
    "Numero di laureati",
    "Tasso di occupazione",
]

READY_SCATTER_COLUMNS = [
    "Color_field",
    "Avg. Retribuzione mensile netta",
    "Avg. Tasso di occupazione",
    "Sum of Numero di laureati",
]


def clean_text(value):
    value = unescape(str(value)).replace("\xa0", " ")
    return " ".join(value.split())


def normalize_label(value):
    value = clean_text(value).lower()
    return re.sub(r"\s+", " ", value)


def parse_number(value):
    value = clean_text(value)
    if not value or value in {"-", "n.d.", "n.d"}:
        return None
    value = re.sub(r"\(\d+\)$", "", value).strip()
    value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def as_int_if_whole(value):
    if value is None:
        return None
    if float(value).is_integer():
        return int(value)
    return value


def slugify(value):
    value = normalize_label(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown"


def display_group(value):
    value = clean_text(value).replace(" - ", "-")
    if value == "*":
        return value
    value = value.lower()
    value = value[:1].upper() + value[1:]
    value = value.replace(" ict", " ICT")
    return value


def display_course_type(value):
    value = clean_text(value)
    labels = {
        "*": "*",
        "laurea di primo livello": "Laurea di primo livello",
        "laurea magistrale a ciclo unico": "Laurea magistrale a ciclo unico",
        "laurea magistrale biennale": "Laurea magistrale biennale",
    }
    return labels.get(normalize_label(value), value)


def fetch_url(url, retries=3, timeout=60, pause=1.5):
    last_error = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (HTTPError, TimeoutError, URLError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"Could not fetch {url}") from last_error


def parse_select_options(html):
    soup = BeautifulSoup(html, "html.parser")
    options_by_name = {}

    for select in soup.find_all("select"):
        name = select.get("name")
        if not name:
            continue
        options_by_name.setdefault(name, [])
        for option in select.find_all("option"):
            options_by_name[name].append(
                {
                    "name": name,
                    "value": option.get("value", ""),
                    "text": clean_text(option.get_text(" ", strip=True)),
                }
            )

    return options_by_name


def get_options(config, survey_year):
    params = {"config": config, "anno": survey_year, "lang": "it"}
    url = f"{BASE_URL}/solotendine.php?{urlencode(params)}"
    return parse_select_options(fetch_url(url))


def get_available_survey_years(config="occupazione", reference_year=2022):
    options = get_options(config=config, survey_year=reference_year)
    years = []
    for option in options.get("anno", []):
        value = str(option["value"])
        if value.isdigit():
            years.append(int(value))
    return sorted(set(years), reverse=True)


def resolve_survey_year(survey_year, use_latest_survey_year=False):
    if use_latest_survey_year or normalize_label(survey_year) in {"latest", "ultimo", "last"}:
        years = get_available_survey_years()
        if not years:
            raise ValueError("No AlmaLaurea survey years found")
        return years[0]
    return int(survey_year)


def build_visualizza_url(
    survey_year,
    years_after_degree,
    university_code,
    group_code,
    disaggregation="corstipo",
    course_type_code="tutti",
):
    params = {
        **DEFAULT_VISUALIZZA_PARAMS,
        "anno": str(survey_year),
        "annolau": str(years_after_degree),
        "ateneo": university_code,
        "gruppo": group_code,
        "disaggregazione": disaggregation,
        "corstipo": course_type_code,
    }
    return f"{BASE_URL}/visualizza.php?{urlencode(params)}"


def table_section_id(table):
    classes = " ".join(table.get("class", []))
    match = re.search(r"datiprofilo(\d+)", classes)
    if not match:
        return None
    return int(match.group(1))


def cell_text(cell):
    return clean_text(cell.get_text(" ", strip=True))


def row_cells(row):
    return row.find_all(["td", "th"], recursive=False)


def table_rows(table):
    return table.find_all("tr")


def table_headers(table):
    html = str(table)
    regex_headers = []
    for match in re.finditer(
        r"<span\s+onmouseover=(?P<quote>[\"'])return escape\('(?P<title>[\s\S]*?)'\);(?P=quote)[^>]*>(?P<label>[\s\S]*?)</span>",
        html,
    ):
        title = unescape(match.group("title"))
        if not any(
            marker in title
            for marker in [
                "<b>tipo di corso</b>:",
                "<b>gruppo disciplinare</b>:",
                "<b>Ateneo</b>:",
                "<b>classe di laurea</b>:",
            ]
        ):
            continue
        label_html = match.group("label")
        label_text = BeautifulSoup(label_html, "html.parser").get_text(" ", strip=True)
        regex_headers.append(clean_text(label_text))

    if regex_headers:
        return ["*"] + regex_headers

    for row in table_rows(table):
        headers = []
        for cell in row_cells(row):
            classes = cell.get("class", [])
            if "header2" in classes:
                text = cell_text(cell)
                if text:
                    headers.append(text)
        if headers:
            return ["*"] + headers
    return ["*"]


def row_values(row):
    cells = row_cells(row)
    return [parse_number(cell_text(cell)) for cell in cells[1:]]


def set_metric(records, headers, values, metric_name):
    for index, header in enumerate(headers):
        records.setdefault(header, {})
        records[header][metric_name] = values[index] if index < len(values) else None


def parse_tables(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find_all("table")


def extract_metrics_by_definition(html):
    tables = parse_tables(html)
    graduates_by_header = {}
    metrics = {
        "restrictive": {},
        "broad": {},
    }

    for table in tables:
        if table_section_id(table) != 1:
            continue
        headers = table_headers(table)
        for row in table_rows(table):
            cells = row_cells(row)
            if not cells:
                continue
            if normalize_label(cell_text(cells[0])) == "numero di laureati":
                set_metric(graduates_by_header, headers, row_values(row), "graduates")
                break

    for table in tables:
        section_id = table_section_id(table)
        definition = DEFINITION_BY_SECTION.get(section_id)
        if not definition:
            continue

        headers = table_headers(table)
        current_indicator = None

        for row in table_rows(table):
            cells = row_cells(row)
            if not cells:
                continue
            label = normalize_label(cell_text(cells[0]))

            if label.startswith("tasso di occupazione"):
                current_indicator = "employment_rate"
                continue
            if label.startswith("retribuzione mensile netta"):
                current_indicator = "net_monthly_salary"
                continue
            if label == "totale" and current_indicator:
                set_metric(metrics[definition], headers, row_values(row), current_indicator)
                current_indicator = None

    for definition_records in metrics.values():
        for header, graduate_values in graduates_by_header.items():
            definition_records.setdefault(header, {}).update(graduate_values)

    return metrics


def course_type_code(course_type):
    normalized = normalize_label(course_type)
    return COURSE_TYPE_CODES.get(normalized, slugify(course_type))


def scrape_one_combination(
    survey_year,
    years_after_degree,
    university,
    group,
    definitions,
):
    source_url = build_visualizza_url(
        survey_year=survey_year,
        years_after_degree=years_after_degree,
        university_code=university["value"],
        group_code=group["value"],
    )
    html = fetch_url(source_url)
    metrics_by_definition = extract_metrics_by_definition(html)
    graduation_year = survey_year - years_after_degree

    rows = []
    for definition, course_metrics in metrics_by_definition.items():
        if definition not in definitions:
            continue
        for course_type, values in course_metrics.items():
            has_data = any(
                values.get(metric) is not None
                for metric in ["graduates", "employment_rate", "net_monthly_salary"]
            )
            if not has_data:
                continue

            rows.append(
                {
                    "survey_year": survey_year,
                    "years_after_degree": years_after_degree,
                    "graduation_year": graduation_year,
                    "employment_definition": definition,
                    "employment_definition_label": DEFINITION_LABELS[definition],
                    "university_code": university["value"],
                    "university": "*" if university["value"] == "tutti" else university["text"],
                    "disciplinary_group_code": group["value"],
                    "disciplinary_group": group["text"],
                    "course_type_code": course_type_code(course_type),
                    "course_type": course_type,
                    "degree_class_code": "tutti",
                    "degree_class": "*",
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "source_url": source_url,
                }
            )
    return rows


def selected_options(options, include_total, limit):
    selected = [option for option in options if include_total or option["value"] != "tutti"]
    if limit is not None:
        selected = selected[:limit]
    return selected


def scrape_dashboard_dataset(
    survey_year,
    years_after_degree_values,
    definitions,
    include_total_university=True,
    include_total_group=False,
    limit_universities=None,
    limit_groups=None,
    workers=4,
):
    options = get_options(config="occupazione", survey_year=survey_year)
    universities = selected_options(
        options.get("ateneo", []),
        include_total=include_total_university,
        limit=limit_universities,
    )
    groups = selected_options(
        options.get("gruppo", []),
        include_total=include_total_group,
        limit=limit_groups,
    )
    tasks = [
        (years_after_degree, university, group)
        for years_after_degree in years_after_degree_values
        for university in universities
        for group in groups
    ]

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                scrape_one_combination,
                survey_year,
                years_after_degree,
                university,
                group,
                set(definitions),
            ): (years_after_degree, university, group)
            for years_after_degree, university, group in tasks
        }
        for index, future in enumerate(as_completed(future_to_task), start=1):
            years_after_degree, university, group = future_to_task[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(
                    "WARNING: skipped",
                    f"annolau={years_after_degree}",
                    f"ateneo={university['value']}",
                    f"gruppo={group['value']}",
                    f"reason={exc}",
                )
            if index % 25 == 0 or index == len(tasks):
                print(f"Completed {index}/{len(tasks)} AlmaLaurea pages")

    rows.sort(
        key=lambda row: (
            row["survey_year"],
            row["years_after_degree"],
            row["employment_definition"],
            str(row["disciplinary_group"]),
            str(row["university"]),
            str(row["course_type"]),
        )
    )
    return rows, options


def scrape_one_group_course_by_university(
    survey_year,
    years_after_degree,
    group,
    course_type,
    university_code_by_name,
    definitions,
):
    source_url = build_visualizza_url(
        survey_year=survey_year,
        years_after_degree=years_after_degree,
        university_code="tutti",
        group_code=group["value"],
        disaggregation="ateneo",
        course_type_code=course_type["value"],
    )
    html = fetch_url(source_url)
    metrics_by_definition = extract_metrics_by_definition(html)
    graduation_year = survey_year - years_after_degree
    course_type_label = "*" if course_type["value"] == "tutti" else course_type["text"]

    rows = []
    for definition, university_metrics in metrics_by_definition.items():
        if definition not in definitions:
            continue
        for university, values in university_metrics.items():
            has_data = any(
                values.get(metric) is not None
                for metric in ["graduates", "employment_rate", "net_monthly_salary"]
            )
            if not has_data:
                continue

            university_name = "*" if university == "*" else university
            rows.append(
                {
                    "survey_year": survey_year,
                    "years_after_degree": years_after_degree,
                    "graduation_year": graduation_year,
                    "employment_definition": definition,
                    "employment_definition_label": DEFINITION_LABELS[definition],
                    "university_code": (
                        "tutti" if university_name == "*" else university_code_by_name.get(university_name, "")
                    ),
                    "university": university_name,
                    "disciplinary_group_code": group["value"],
                    "disciplinary_group": group["text"],
                    "course_type_code": course_type["value"],
                    "course_type": course_type_label,
                    "degree_class_code": "tutti",
                    "degree_class": "*",
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "source_url": source_url,
                }
            )
    return rows


def scrape_dashboard_dataset_by_university(
    survey_year,
    years_after_degree_values,
    definitions,
    include_total_group=False,
    limit_groups=None,
    limit_course_types=None,
    workers=4,
):
    options = get_options(config="occupazione", survey_year=survey_year)
    groups = selected_options(
        options.get("gruppo", []),
        include_total=include_total_group,
        limit=limit_groups,
    )
    course_types = selected_options(
        options.get("corstipo", []),
        include_total=True,
        limit=limit_course_types,
    )
    university_code_by_name = {
        option["text"]: option["value"]
        for option in options.get("ateneo", [])
        if option["value"] != "tutti"
    }

    tasks = [
        (years_after_degree, group, course_type)
        for years_after_degree in years_after_degree_values
        for group in groups
        for course_type in course_types
    ]

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                scrape_one_group_course_by_university,
                survey_year,
                years_after_degree,
                group,
                course_type,
                university_code_by_name,
                set(definitions),
            ): (years_after_degree, group, course_type)
            for years_after_degree, group, course_type in tasks
        }
        for index, future in enumerate(as_completed(future_to_task), start=1):
            years_after_degree, group, course_type = future_to_task[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(
                    "WARNING: skipped",
                    f"annolau={years_after_degree}",
                    f"gruppo={group['value']}",
                    f"corstipo={course_type['value']}",
                    f"reason={exc}",
                )
            if index % 25 == 0 or index == len(tasks):
                print(f"Completed {index}/{len(tasks)} AlmaLaurea pages")

    rows.sort(
        key=lambda row: (
            row["survey_year"],
            row["years_after_degree"],
            row["employment_definition"],
            str(row["disciplinary_group"]),
            str(row["university"]),
            str(row["course_type"]),
        )
    )
    return rows, options


def scrape_one_group_course_by_degree_class(
    survey_year,
    years_after_degree,
    group,
    course_type,
    definitions,
):
    source_url = build_visualizza_url(
        survey_year=survey_year,
        years_after_degree=years_after_degree,
        university_code="tutti",
        group_code=group["value"],
        disaggregation="classe",
        course_type_code=course_type["value"],
    )
    html = fetch_url(source_url)
    metrics_by_definition = extract_metrics_by_definition(html)
    graduation_year = survey_year - years_after_degree
    course_type_label = "*" if course_type["value"] == "tutti" else course_type["text"]

    rows = []
    for definition, degree_class_metrics in metrics_by_definition.items():
        if definition not in definitions:
            continue
        for degree_class, values in degree_class_metrics.items():
            if degree_class == "*":
                continue
            has_data = any(
                values.get(metric) is not None
                for metric in ["graduates", "employment_rate", "net_monthly_salary"]
            )
            if not has_data:
                continue

            rows.append(
                {
                    "survey_year": survey_year,
                    "years_after_degree": years_after_degree,
                    "graduation_year": graduation_year,
                    "employment_definition": definition,
                    "employment_definition_label": DEFINITION_LABELS[definition],
                    "university_code": "tutti",
                    "university": "*",
                    "disciplinary_group_code": group["value"],
                    "disciplinary_group": group["text"],
                    "course_type_code": course_type["value"],
                    "course_type": course_type_label,
                    "degree_class_code": slugify(degree_class),
                    "degree_class": degree_class,
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "source_url": source_url,
                }
            )
    return rows


def scrape_degree_class_dataset(
    survey_year,
    years_after_degree_values,
    definitions,
    include_total_group=False,
    limit_groups=None,
    limit_course_types=None,
    workers=4,
):
    options = get_options(config="occupazione", survey_year=survey_year)
    groups = selected_options(
        options.get("gruppo", []),
        include_total=include_total_group,
        limit=limit_groups,
    )
    course_types = selected_options(
        options.get("corstipo", []),
        include_total=True,
        limit=limit_course_types,
    )
    tasks = [
        (years_after_degree, group, course_type)
        for years_after_degree in years_after_degree_values
        for group in groups
        for course_type in course_types
    ]

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                scrape_one_group_course_by_degree_class,
                survey_year,
                years_after_degree,
                group,
                course_type,
                set(definitions),
            ): (years_after_degree, group, course_type)
            for years_after_degree, group, course_type in tasks
        }
        for index, future in enumerate(as_completed(future_to_task), start=1):
            years_after_degree, group, course_type = future_to_task[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(
                    "WARNING: skipped degree classes",
                    f"annolau={years_after_degree}",
                    f"gruppo={group['value']}",
                    f"corstipo={course_type['value']}",
                    f"reason={exc}",
                )
            if index % 25 == 0 or index == len(tasks):
                print(f"Completed {index}/{len(tasks)} AlmaLaurea degree-class pages")

    rows.sort(
        key=lambda row: (
            row["survey_year"],
            row["years_after_degree"],
            row["employment_definition"],
            str(row["disciplinary_group"]),
            str(row["course_type"]),
            str(row["degree_class"]),
        )
    )
    return rows, options


def write_csv(path, rows, columns=OUTPUT_COLUMNS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return list(csv.DictReader(input_file))


def infer_survey_year(rows):
    years = sorted({int(float(row["survey_year"])) for row in rows if row.get("survey_year")})
    if len(years) != 1:
        raise ValueError(f"Expected one survey year, found: {years}")
    return years[0]


def write_lookup_csv(path, options):
    rows = [
        {"dimension": name, "code": option["value"], "label": option["text"]}
        for name, values in options.items()
        for option in values
        if name in {"anno", "annolau", "livello", "corstipo", "ateneo", "gruppo"}
    ]
    write_csv(path, rows, columns=["dimension", "code", "label"])


def ready_boxplot_rows(rows, graduation_year, definition):
    output = []
    for row in rows:
        if int(float(row["graduation_year"])) != int(graduation_year):
            continue
        if row["employment_definition"] != definition:
            continue
        if row["disciplinary_group_code"] == "tutti":
            continue
        if row.get("degree_class", "*") != "*":
            continue

        group = display_group(row["disciplinary_group"])
        output.append(
            {
                "Color_field": group,
                "Retribuzione mensile netta": row["net_monthly_salary"],
                "Ateneo": row["university"],
                "Gruppo disciplinare": group,
                "Tipo di corso": display_course_type(row["course_type"]),
                "Numero di laureati": row["graduates"],
                "Tasso di occupazione": row["employment_rate"],
            }
        )
    return output


def ready_scatter_rows(boxplot_rows):
    grouped = {}
    for row in boxplot_rows:
        if row["Ateneo"] != "*" or row["Tipo di corso"] != "*":
            continue

        group = row["Color_field"]
        grouped.setdefault(
            group,
            {
                "salary_values": [],
                "employment_values": [],
                "graduates": 0,
            },
        )
        if row["Retribuzione mensile netta"] not in {None, ""}:
            grouped[group]["salary_values"].append(float(row["Retribuzione mensile netta"]))
        if row["Tasso di occupazione"] not in {None, ""}:
            grouped[group]["employment_values"].append(float(row["Tasso di occupazione"]))
        if row["Numero di laureati"] not in {None, ""}:
            grouped[group]["graduates"] += int(float(row["Numero di laureati"]))

    output = []
    for group, values in sorted(grouped.items()):
        salary_values = values["salary_values"]
        employment_values = values["employment_values"]
        output.append(
            {
                "Color_field": group,
                "Avg. Retribuzione mensile netta": (
                    sum(salary_values) / len(salary_values) if salary_values else None
                ),
                "Avg. Tasso di occupazione": (
                    sum(employment_values) / len(employment_values) if employment_values else None
                ),
                "Sum of Numero di laureati": values["graduates"],
            }
        )
    return output


def write_ready_csvs(rows, output_dir, definition, survey_year):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    graduation_years = sorted({int(float(row["graduation_year"])) for row in rows})

    for graduation_year in graduation_years:
        boxplot_rows = ready_boxplot_rows(rows, graduation_year, definition)
        scatter_rows = ready_scatter_rows(boxplot_rows)
        years_after_degree = survey_year - graduation_year
        base_name = (
            f"almalaurea_survey_{survey_year}"
            f"__laureati_{graduation_year}"
            f"__annolau_{years_after_degree}"
            f"__{definition}"
        )

        write_csv(
            output_dir / f"{base_name}__boxplot.csv",
            boxplot_rows,
            columns=READY_BOXPLOT_COLUMNS,
        )
        write_csv(
            output_dir / f"{base_name}__scatter.csv",
            scatter_rows,
            columns=READY_SCATTER_COLUMNS,
        )
