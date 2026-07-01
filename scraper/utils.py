from __future__ import annotations

import csv
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import IncompleteRead
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
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

EXCLUDED_COURSE_TYPE_CODES = {"CDL2"}
LSE_GROUP_CODES = {"1", "3", "8", "11", "13", "14"}

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
    "degree_course_code",
    "degree_course",
    "graduates",
    "employment_rate",
    "net_monthly_salary",
    "second_level_enrollment_rate",
    "current_second_level_enrollment_rate",
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
    "Iscritti a laurea magistrale",
    "Attualmente iscritti a laurea magistrale",
]

READY_SCATTER_COLUMNS = [
    "Color_field",
    "Avg. Retribuzione mensile netta",
    "Avg. Tasso di occupazione",
    "Avg. Iscritti a laurea magistrale",
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
        except (HTTPError, IncompleteRead, TimeoutError, URLError) as exc:
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


def get_selection_options(config="occupazione", **params):
    query = {"config": config, "lang": "it"}
    query.update({
        name: value
        for name, value in params.items()
        if value not in {None, ""}
    })
    url = f"{BASE_URL}/solotendine.php?{urlencode(query)}"
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
    class_code="tutti",
    post_course_code="tutti",
):
    # AlmaLaurea's legacy endpoint is order-sensitive: the official form
    # redirects to visualizza.php with CONFIG at the end of the query string.
    params = [
        ("anno", str(survey_year)),
        ("corstipo", course_type_code),
        ("ateneo", university_code),
        ("facolta", DEFAULT_VISUALIZZA_PARAMS["facolta"]),
        ("gruppo", group_code),
        ("livello", DEFAULT_VISUALIZZA_PARAMS["livello"]),
        ("area4", DEFAULT_VISUALIZZA_PARAMS["area4"]),
        ("pa", DEFAULT_VISUALIZZA_PARAMS["pa"]),
        ("classe", class_code),
        ("postcorso", post_course_code),
        ("annolau", str(years_after_degree)),
        ("isstella", DEFAULT_VISUALIZZA_PARAMS["isstella"]),
        ("condocc", DEFAULT_VISUALIZZA_PARAMS["condocc"]),
        ("iscrls", DEFAULT_VISUALIZZA_PARAMS["iscrls"]),
        ("disaggregazione", disaggregation),
        ("LANG", "it"),
        ("CONFIG", DEFAULT_VISUALIZZA_PARAMS["CONFIG"]),
    ]
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
                "<b>corso di laurea</b>:",
            ]
        ):
            continue
        label_html = match.group("label")
        if "<" in label_html:
            label_text = BeautifulSoup(label_html, "html.parser").get_text(" ", strip=True)
        else:
            label_text = label_html
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
    second_level_by_header = {}
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
        if table_section_id(table) != 2:
            continue
        headers = table_headers(table)
        waiting_for_current_second_level = False
        for row in table_rows(table):
            cells = row_cells(row)
            if not cells:
                continue
            label = normalize_label(cell_text(cells[0]))

            if label.startswith("si sono iscritti ad un corso di laurea di secondo livello"):
                set_metric(
                    second_level_by_header,
                    headers,
                    row_values(row),
                    "second_level_enrollment_rate",
                )
                waiting_for_current_second_level = True
                continue

            if label == "sono attualmente iscritti" and waiting_for_current_second_level:
                set_metric(
                    second_level_by_header,
                    headers,
                    row_values(row),
                    "current_second_level_enrollment_rate",
                )
                waiting_for_current_second_level = False
                continue

            if label.startswith("si sono iscritti ad un corso di laurea di primo livello"):
                waiting_for_current_second_level = False

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
                values = row_values(row)
                if any(value is not None for value in values):
                    set_metric(metrics[definition], headers, values, "employment_rate")
                    current_indicator = None
                else:
                    current_indicator = "employment_rate"
                continue
            if label.startswith("retribuzione mensile netta"):
                values = row_values(row)
                if any(value is not None for value in values):
                    set_metric(metrics[definition], headers, values, "net_monthly_salary")
                    current_indicator = None
                else:
                    current_indicator = "net_monthly_salary"
                continue
            if label == "totale" and current_indicator:
                set_metric(metrics[definition], headers, row_values(row), current_indicator)
                current_indicator = None

    for definition_records in metrics.values():
        for header, graduate_values in graduates_by_header.items():
            definition_records.setdefault(header, {}).update(graduate_values)
        for header, second_level_values in second_level_by_header.items():
            definition_records.setdefault(header, {}).update(second_level_values)

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
                for metric in [
                    "graduates",
                    "employment_rate",
                    "net_monthly_salary",
                    "second_level_enrollment_rate",
                ]
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
                    "degree_course_code": "tutti",
                    "degree_course": "*",
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "second_level_enrollment_rate": values.get("second_level_enrollment_rate"),
                    "current_second_level_enrollment_rate": values.get(
                        "current_second_level_enrollment_rate"
                    ),
                    "source_url": source_url,
                }
            )
    return rows


def selected_options(options, include_total, limit):
    selected = [option for option in options if include_total or option["value"] != "tutti"]
    if limit is not None:
        selected = selected[:limit]
    return selected


def valid_course_type_task(years_after_degree, group, course_type):
    course_type_value = str(course_type["value"])
    group_value = str(group["value"])

    if course_type_value in EXCLUDED_COURSE_TYPE_CODES:
        return False
    if course_type_value == "L" and int(years_after_degree) != 1:
        return False
    if course_type_value == "LSE" and group_value not in LSE_GROUP_CODES:
        return False
    return True


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
                for metric in [
                    "graduates",
                    "employment_rate",
                    "net_monthly_salary",
                    "second_level_enrollment_rate",
                ]
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
                    "degree_course_code": "tutti",
                    "degree_course": "*",
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "second_level_enrollment_rate": values.get("second_level_enrollment_rate"),
                    "current_second_level_enrollment_rate": values.get(
                        "current_second_level_enrollment_rate"
                    ),
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
        if valid_course_type_task(years_after_degree, group, course_type)
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
    university,
    group,
    course_type,
    definitions,
):
    source_url = build_visualizza_url(
        survey_year=survey_year,
        years_after_degree=years_after_degree,
        university_code=university["value"],
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
                for metric in [
                    "graduates",
                    "employment_rate",
                    "net_monthly_salary",
                    "second_level_enrollment_rate",
                ]
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
                    "course_type_code": course_type["value"],
                    "course_type": course_type_label,
                    "degree_class_code": slugify(degree_class),
                    "degree_class": degree_class,
                    "degree_course_code": "tutti",
                    "degree_course": "*",
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "second_level_enrollment_rate": values.get("second_level_enrollment_rate"),
                    "current_second_level_enrollment_rate": values.get(
                        "current_second_level_enrollment_rate"
                    ),
                    "source_url": source_url,
                }
            )
    return rows


def row_has_downloaded_metrics(row):
    return any(
        row.get(metric) not in {None, "", 0, "0", "0.0"}
        for metric in [
            "graduates",
            "employment_rate",
            "net_monthly_salary",
            "second_level_enrollment_rate",
        ]
    )


def degree_class_tasks_from_base_rows(base_rows):
    tasks_by_key = {}
    for row in base_rows:
        if row.get("degree_class", "*") != "*":
            continue
        if row.get("disciplinary_group_code") in {"", "tutti"}:
            continue
        if not row_has_downloaded_metrics(row):
            continue

        key = (
            int(row["years_after_degree"]),
            str(row["university_code"]),
            str(row["disciplinary_group_code"]),
            str(row["course_type_code"]),
        )
        if key in tasks_by_key:
            continue

        university_label = "*" if row["university_code"] == "tutti" else row["university"]
        course_type_label = "*" if row["course_type_code"] == "tutti" else row["course_type"]
        tasks_by_key[key] = (
            int(row["years_after_degree"]),
            {
                "value": row["university_code"],
                "text": university_label,
            },
            {
                "value": row["disciplinary_group_code"],
                "text": row["disciplinary_group"],
            },
            {
                "value": row["course_type_code"],
                "text": course_type_label,
            },
        )
    return sorted(
        tasks_by_key.values(),
        key=lambda task: (
            task[0],
            str(task[2]["text"]),
            str(task[3]["text"]),
            str(task[1]["text"]),
        ),
    )


def codes_in_parentheses(value):
    codes = []
    for group in re.findall(r"\(([^()]*)\)", value or ""):
        codes.extend(code.strip() for code in group.split(",") if code.strip())
    return codes


def degree_class_for_course(course_label, class_options):
    course_codes = codes_in_parentheses(course_label)
    if not course_codes:
        return None
    for option in class_options:
        if option["value"] == "tutti":
            continue
        class_label = option["text"]
        class_codes = codes_in_parentheses(class_label)
        if any(code in class_codes for code in course_codes):
            return class_label
    return None


def scrape_one_group_course_by_degree_course(
    survey_year,
    years_after_degree,
    university,
    group,
    course_type,
    definitions,
):
    if course_type["value"] == "tutti":
        return []

    try:
        selection_options = get_selection_options(
            config="occupazione",
            anno=survey_year,
            corstipo=course_type["value"],
            ateneo=university["value"],
            gruppo=group["value"],
            annolau=years_after_degree,
        )
    except Exception as exc:
        print(
            "WARNING: degree-course options unavailable",
            f"annolau={years_after_degree}",
            f"ateneo={university['value']}",
            f"gruppo={group['value']}",
            f"corstipo={course_type['value']}",
            f"reason={exc}",
        )
        selection_options = {}
    class_options = selection_options.get("classe", [])
    course_code_by_label = {
        option["text"]: option["value"]
        for option in selection_options.get("postcorso", [])
        if option["value"] != "tutti"
    }
    source_url = build_visualizza_url(
        survey_year=survey_year,
        years_after_degree=years_after_degree,
        university_code=university["value"],
        group_code=group["value"],
        disaggregation="postcorso",
        course_type_code=course_type["value"],
    )
    html = fetch_url(source_url)
    metrics_by_definition = extract_metrics_by_definition(html)
    graduation_year = survey_year - years_after_degree

    rows = []
    for definition, course_metrics in metrics_by_definition.items():
        if definition not in definitions:
            continue
        for degree_course, values in course_metrics.items():
            if degree_course == "*":
                continue
            has_data = any(
                values.get(metric) is not None
                for metric in [
                    "graduates",
                    "employment_rate",
                    "net_monthly_salary",
                    "second_level_enrollment_rate",
                ]
            )
            if not has_data:
                continue

            degree_class = degree_class_for_course(degree_course, class_options) or "*"
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
                    "course_type_code": course_type["value"],
                    "course_type": course_type["text"],
                    "degree_class_code": "tutti" if degree_class == "*" else slugify(degree_class),
                    "degree_class": degree_class,
                    "degree_course_code": course_code_by_label.get(
                        degree_course,
                        slugify(degree_course),
                    ),
                    "degree_course": degree_course,
                    "graduates": as_int_if_whole(values.get("graduates")),
                    "employment_rate": values.get("employment_rate"),
                    "net_monthly_salary": values.get("net_monthly_salary"),
                    "second_level_enrollment_rate": values.get("second_level_enrollment_rate"),
                    "current_second_level_enrollment_rate": values.get(
                        "current_second_level_enrollment_rate"
                    ),
                    "source_url": source_url,
                }
            )
    return rows


def degree_course_tasks_from_base_rows(base_rows):
    tasks_by_key = {}
    for row in base_rows:
        if row.get("degree_class", "*") != "*":
            continue
        if row.get("course_type_code") in {"", "tutti"}:
            continue
        if row.get("disciplinary_group_code") in {"", "tutti"}:
            continue
        if not row_has_downloaded_metrics(row):
            continue

        key = (
            int(row["years_after_degree"]),
            str(row["university_code"]),
            str(row["disciplinary_group_code"]),
            str(row["course_type_code"]),
        )
        if key in tasks_by_key:
            continue

        university_label = "*" if row["university_code"] == "tutti" else row["university"]
        tasks_by_key[key] = (
            int(row["years_after_degree"]),
            {
                "value": row["university_code"],
                "text": university_label,
            },
            {
                "value": row["disciplinary_group_code"],
                "text": row["disciplinary_group"],
            },
            {
                "value": row["course_type_code"],
                "text": row["course_type"],
            },
        )
    return sorted(
        tasks_by_key.values(),
        key=lambda task: (
            task[0],
            str(task[2]["text"]),
            str(task[3]["text"]),
            str(task[1]["text"]),
        ),
    )


def scrape_degree_class_dataset(
    survey_year,
    years_after_degree_values,
    definitions,
    base_rows=None,
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
    if base_rows is not None:
        tasks = degree_class_tasks_from_base_rows(base_rows)
    else:
        universities = selected_options(
            options.get("ateneo", []),
            include_total=True,
            limit=None,
        )
        tasks = [
            (years_after_degree, university, group, course_type)
            for years_after_degree in years_after_degree_values
            for university in universities
            for group in groups
            for course_type in course_types
            if valid_course_type_task(years_after_degree, group, course_type)
        ]

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                scrape_one_group_course_by_degree_class,
                survey_year,
                years_after_degree,
                university,
                group,
                course_type,
                set(definitions),
            ): (years_after_degree, university, group, course_type)
            for years_after_degree, university, group, course_type in tasks
        }
        for index, future in enumerate(as_completed(future_to_task), start=1):
            years_after_degree, university, group, course_type = future_to_task[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(
                    "WARNING: skipped degree classes",
                    f"annolau={years_after_degree}",
                    f"ateneo={university['value']}",
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
            str(row["university"]),
        )
    )
    return rows, options


def scrape_degree_course_dataset(
    survey_year,
    years_after_degree_values,
    definitions,
    base_rows=None,
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
    if base_rows is not None:
        tasks = degree_course_tasks_from_base_rows(base_rows)
    else:
        universities = selected_options(
            options.get("ateneo", []),
            include_total=True,
            limit=None,
        )
        tasks = [
            (years_after_degree, university, group, course_type)
            for years_after_degree in years_after_degree_values
            for university in universities
            for group in groups
            for course_type in course_types
            if (
                course_type["value"] != "tutti"
                and valid_course_type_task(years_after_degree, group, course_type)
            )
        ]

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(
                scrape_one_group_course_by_degree_course,
                survey_year,
                years_after_degree,
                university,
                group,
                course_type,
                set(definitions),
            ): (years_after_degree, university, group, course_type)
            for years_after_degree, university, group, course_type in tasks
        }
        for index, future in enumerate(as_completed(future_to_task), start=1):
            years_after_degree, university, group, course_type = future_to_task[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(
                    "WARNING: skipped degree courses",
                    f"annolau={years_after_degree}",
                    f"ateneo={university['value']}",
                    f"gruppo={group['value']}",
                    f"corstipo={course_type['value']}",
                    f"reason={exc}",
                )
            if index % 25 == 0 or index == len(tasks):
                print(f"Completed {index}/{len(tasks)} AlmaLaurea degree-course pages")

    rows.sort(
        key=lambda row: (
            row["survey_year"],
            row["years_after_degree"],
            row["employment_definition"],
            str(row["disciplinary_group"]),
            str(row["course_type"]),
            str(row["degree_class"]),
            str(row["degree_course"]),
            str(row["university"]),
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


def is_first_level_row(row):
    return (
        row.get("course_type_code") == "L"
        or normalize_label(row.get("course_type", "")) == "laurea di primo livello"
    )


def row_second_level_header(row):
    if row.get("degree_class", "*") not in {"", "*"}:
        return row.get("degree_class")
    university = row.get("university", "*")
    return "*" if university in {"", "*"} else university


def second_level_metrics_from_url(source_url):
    html = fetch_url(source_url)
    metrics_by_definition = extract_metrics_by_definition(html)
    output = {}

    for definition_metrics in metrics_by_definition.values():
        for header, values in definition_metrics.items():
            second_level = values.get("second_level_enrollment_rate")
            current_second_level = values.get("current_second_level_enrollment_rate")
            if second_level is None and current_second_level is None:
                continue
            output[header] = {
                "second_level_enrollment_rate": second_level,
                "current_second_level_enrollment_rate": current_second_level,
            }
    return output


def enrich_rows_with_second_level_metrics(rows, workers=8):
    source_urls = sorted({
        row.get("source_url")
        for row in rows
        if is_first_level_row(row) and row.get("source_url")
    })
    metrics_by_url = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {
            executor.submit(second_level_metrics_from_url, source_url): source_url
            for source_url in source_urls
        }
        for index, future in enumerate(as_completed(future_to_url), start=1):
            source_url = future_to_url[future]
            try:
                metrics_by_url[source_url] = future.result()
            except Exception as exc:
                params = parse_qs(urlparse(source_url).query)
                print(
                    "WARNING: skipped second-level enrichment",
                    f"anno={params.get('anno', [''])[0]}",
                    f"annolau={params.get('annolau', [''])[0]}",
                    f"gruppo={params.get('gruppo', [''])[0]}",
                    f"disaggregazione={params.get('disaggregazione', [''])[0]}",
                    f"reason={exc}",
                )
            if index % 25 == 0 or index == len(source_urls):
                print(f"Completed {index}/{len(source_urls)} second-level enrichment pages")

    for row in rows:
        if not is_first_level_row(row):
            row.setdefault("second_level_enrollment_rate", None)
            row.setdefault("current_second_level_enrollment_rate", None)
            continue

        url_metrics = metrics_by_url.get(row.get("source_url"), {})
        values = url_metrics.get(row_second_level_header(row), {})
        row["second_level_enrollment_rate"] = values.get("second_level_enrollment_rate")
        row["current_second_level_enrollment_rate"] = values.get(
            "current_second_level_enrollment_rate"
        )

    return rows


def enrich_csv_with_second_level_metrics(input_csv, output_csv=None, workers=8):
    input_csv = Path(input_csv)
    output_csv = Path(output_csv) if output_csv is not None else input_csv
    rows = read_csv(input_csv)
    rows = enrich_rows_with_second_level_metrics(rows=rows, workers=workers)
    write_csv(output_csv, rows)
    print(f"Enriched {len(rows)} rows with second-level metrics in {output_csv}")


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
        if row.get("degree_course", "*") != "*":
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
                "Iscritti a laurea magistrale": row.get("second_level_enrollment_rate"),
                "Attualmente iscritti a laurea magistrale": row.get(
                    "current_second_level_enrollment_rate"
                ),
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
                "second_level_values": [],
                "graduates": 0,
            },
        )
        if row["Retribuzione mensile netta"] not in {None, ""}:
            grouped[group]["salary_values"].append(float(row["Retribuzione mensile netta"]))
        if row["Tasso di occupazione"] not in {None, ""}:
            grouped[group]["employment_values"].append(float(row["Tasso di occupazione"]))
        if row["Iscritti a laurea magistrale"] not in {None, ""}:
            grouped[group]["second_level_values"].append(float(row["Iscritti a laurea magistrale"]))
        if row["Numero di laureati"] not in {None, ""}:
            grouped[group]["graduates"] += int(float(row["Numero di laureati"]))

    output = []
    for group, values in sorted(grouped.items()):
        salary_values = values["salary_values"]
        employment_values = values["employment_values"]
        second_level_values = values["second_level_values"]
        output.append(
            {
                "Color_field": group,
                "Avg. Retribuzione mensile netta": (
                    sum(salary_values) / len(salary_values) if salary_values else None
                ),
                "Avg. Tasso di occupazione": (
                    sum(employment_values) / len(employment_values) if employment_values else None
                ),
                "Avg. Iscritti a laurea magistrale": (
                    sum(second_level_values) / len(second_level_values) if second_level_values else None
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
