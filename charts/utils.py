from __future__ import annotations

import re
from pathlib import Path
from textwrap import shorten, wrap

import matplotlib.pyplot as plt
import pandas as pd

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None


REQUIRED_COLUMNS = {
    "survey_year",
    "years_after_degree",
    "employment_definition",
    "university",
    "disciplinary_group",
    "course_type",
    "graduates",
    "employment_rate",
    "net_monthly_salary",
}

AUTHOR_LINE = "Elaborazione di Nazareno Lecis"
TABLEAU_RED = "#c8102e"
FIGURE_HEIGHT = 9.6
FIGURE_WIDTH = 20
FIGURE_DPI = 150
TITLE_FONT_SIZE = 19
AXIS_LABEL_FONT_SIZE = 15
TICK_FONT_SIZE = 12
X_TICK_FONT_SIZE = 11
LEGEND_FONT_SIZE = 11
LEGEND_TITLE_FONT_SIZE = 12
FOOTER_FONT_SIZE = 11
POINT_LABEL_FONT_SIZE = 11

COURSE_TYPE_SHORT_LABELS = {
    "laurea di primo livello": "L primo livello",
    "laurea magistrale a ciclo unico": "LM ciclo unico",
    "laurea magistrale biennale": "LM biennale",
}


def load_dashboard_data(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Missing expected columns: {missing_text}")
    if "degree_class" not in data.columns:
        data["degree_class"] = "*"
    return data


def latest_dashboard_csv(data_dir):
    candidates = sorted(
        Path(data_dir).glob("almalaurea_occupazione__survey_*__annolau_*__defs_*.csv")
    )
    if not candidates:
        raise FileNotFoundError(f"No AlmaLaurea master CSV found in {data_dir}")
    return max(
        candidates,
        key=lambda path: int(path.name.split("__survey_")[1].split("__", 1)[0]),
    )


def filter_dashboard_data(
    data: pd.DataFrame,
    years_after_degree: int,
    definition: str,
    include_total_university: bool,
    include_total_course_type: bool,
    university="*",
    disciplinary_group="*",
    course_type="*",
) -> pd.DataFrame:
    filtered = data[
        (data["years_after_degree"] == years_after_degree)
        & (data["employment_definition"] == definition)
    ].copy()
    if not include_total_university:
        filtered = filtered[filtered["university"] != "*"]
    if not include_total_course_type:
        filtered = filtered[filtered["course_type"] != "*"]
    if university != "*":
        filtered = filtered[filtered["university"].astype(str).str.lower() == str(university).lower()]
    if disciplinary_group != "*":
        filtered = filtered[
            filtered["disciplinary_group"].astype(str).str.lower() == str(disciplinary_group).lower()
        ]
    if course_type != "*":
        filtered = filtered[filtered["course_type"].astype(str).str.lower() == str(course_type).lower()]
    return filtered


def keep_total_rows(data: pd.DataFrame, course_type=False, degree_class=True) -> pd.DataFrame:
    filtered = data.copy()
    if course_type and "course_type" in filtered.columns:
        filtered = filtered[filtered["course_type"].fillna("*").astype(str) == "*"]
    if degree_class and "degree_class" in filtered.columns:
        filtered = filtered[filtered["degree_class"].fillna("*").astype(str) == "*"]
    return filtered


def source_year(data):
    if "survey_year" not in data.columns or data.empty:
        return None
    return int(data["survey_year"].dropna().iloc[0])


def add_source_footer(year, years_after_degree=None, graduation_year=None):
    year_text = f" {year}" if year else ""
    plt.figtext(
        0.01,
        0.035,
        f"Fonte: AlmaLaurea{year_text} - {AUTHOR_LINE}",
        ha="left",
        va="bottom",
        fontsize=FOOTER_FONT_SIZE,
        color="#111111",
    )
    if year and years_after_degree is not None and graduation_year:
        plt.figtext(
            0.01,
            0.012,
            (
                "Nota metodologica: coorte di laurea "
                f"{graduation_year} osservata a {years_after_label(years_after_degree)} "
                f"dalla laurea nell'indagine {year} "
                "(anno laurea = anno indagine - anni dalla laurea)."
            ),
            ha="left",
            va="bottom",
            fontsize=FOOTER_FONT_SIZE,
            color="#333333",
        )


def display_filter_value(value):
    return COURSE_TYPE_SHORT_LABELS.get(str(value), str(value))


def filter_label(university="*", disciplinary_group="*", course_type="*"):
    parts = []
    if course_type != "*":
        parts.append(f"tipo corso: {display_filter_value(course_type)}")
    if disciplinary_group != "*":
        parts.append(f"gruppo: {disciplinary_group}")
    if university != "*":
        parts.append(f"ateneo: {university}")
    if not parts:
        return "filtro: totale"
    return "filtro: " + " | ".join(parts)


def years_after_label(years_after_degree):
    return f"{years_after_degree} anno" if years_after_degree == 1 else f"{years_after_degree} anni"


def employment_definition_label(definition):
    labels = {
        "broad": "occupati incl. formazione retribuita",
        "restrictive": "occupati escl. formazione retribuita",
    }
    return labels.get(str(definition), str(definition))


def selected_definition(data):
    if "employment_definition" not in data.columns or data.empty:
        return ""
    values = data["employment_definition"].dropna().astype(str).unique()
    return values[0] if len(values) else ""


def split_dimension_label(split_dimension):
    labels = {
        "disciplinary_group": "gruppo disciplinare",
        "degree_class": "classe di laurea",
    }
    return labels.get(split_dimension, split_dimension)


def degree_class_short_label(value):
    text = str(value)
    match = re.search(r"\(([^()]*)\)\s*$", text)
    if match:
        return match.group(1).split(",")[0].strip()
    return shorten(text, width=24, placeholder="...")


def group_short_label(value):
    labels = {
        "Agrario-Forestale e Veterinario": "Agrario-vet.",
        "Architettura e Ingegneria civile": "Arch.-ing. civ.",
        "Arte e Design": "Arte/design",
        "Economico": "Economico",
        "Educazione e Formazione": "Educazione",
        "Giuridico": "Giuridico",
        "Informatica e Tecnologie ICT": "ICT",
        "Ingegneria industriale e dell'informazione": "Ing. ind.",
        "Letterario-Umanistico": "Letterario",
        "Linguistico": "Linguistico",
        "Medico-Sanitario e Farmaceutico": "Medico",
        "Politico-Sociale e Comunicazione": "Politico-soc.",
        "Psicologico": "Psicologico",
        "Scientifico": "Scientifico",
        "Scienze motorie e sportive": "Motorie",
    }
    return labels.get(str(value), shorten(str(value), width=24, placeholder="..."))


def choose_scatter_split_dimension(data, requested_split_dimension, course_type):
    if requested_split_dimension != "auto":
        return requested_split_dimension
    if course_type != "*" and "degree_class" in data.columns:
        has_degree_classes = data["degree_class"].fillna("*").astype(str).ne("*").any()
        if has_degree_classes:
            return "degree_class"
    return "disciplinary_group"


def scatter_point_count(data, split_dimension):
    if split_dimension == "degree_class":
        if "degree_class" not in data.columns:
            return 0
        return data["degree_class"].fillna("*").astype(str).ne("*").sum()
    return data["disciplinary_group"].dropna().nunique()


def degree_class_groups(data):
    if "degree_class" not in data.columns:
        return []
    filtered = data[data["degree_class"].fillna("*").astype(str) != "*"]
    return sorted(group for group in filtered["disciplinary_group"].dropna().unique())


def chart_title(first_line, years_after_degree, graduation_year, definition, extra_detail, filters):
    method_line = " | ".join(
        [
            f"coorte {graduation_year}",
            f"{years_after_label(years_after_degree)} dalla laurea",
            employment_definition_label(definition),
        ]
    )
    detail_parts = [
        extra_detail,
        filters,
    ]
    detail_line = " | ".join(part for part in detail_parts if part)
    wrapped_detail_line = "\n".join(wrap(detail_line, width=105)) if detail_line else ""
    lines = [
        first_line,
        method_line,
        wrapped_detail_line,
    ]
    return "\n".join(line for line in lines if line)


def slugify(value):
    value = str(value).lower()
    value = value.replace("*", "all")
    value = "".join(char if char.isalnum() else "_" for char in value)
    value = "_".join(part for part in value.split("_") if part)
    return value or "all"


def filename_slug(value, max_length=28):
    labels = {
        "*": "all",
        "laurea di primo livello": "l_primo",
        "laurea magistrale a ciclo unico": "lm_ciclo_unico",
        "laurea magistrale biennale": "lm_biennale",
        "Agrario-Forestale e Veterinario": "agrario_vet",
        "Architettura e Ingegneria civile": "arch_ing_civ",
        "Arte e Design": "arte_design",
        "Economico": "economico",
        "Educazione e Formazione": "educazione",
        "Giuridico": "giuridico",
        "Informatica e Tecnologie ICT": "ict",
        "Ingegneria industriale e dell'informazione": "ing_ind",
        "Letterario-Umanistico": "letterario",
        "Linguistico": "linguistico",
        "Medico-Sanitario e Farmaceutico": "medico",
        "Politico-Sociale e Comunicazione": "politico_soc",
        "Psicologico": "psicologico",
        "Scientifico": "scientifico",
        "Scienze motorie e sportive": "motorie",
    }
    slug = slugify(labels.get(str(value), value))
    return slug[:max_length].rstrip("_") or "all"


def chart_filename(
    prefix,
    survey_year,
    graduation_year,
    years_after_degree,
    definition,
    university,
    disciplinary_group,
    course_type,
):
    parts = [
        prefix,
        f"s{survey_year}",
        f"l{graduation_year}",
        f"a{years_after_degree}",
        definition,
        f"u_{filename_slug(university)}",
        f"g_{filename_slug(disciplinary_group)}",
        f"t_{filename_slug(course_type)}",
    ]
    return "__".join(parts)


def aggregate_filename(survey_year, graduation_year, years_after_degree, definition, filters, split_dimension):
    parts = [
        "scatter",
        f"s{survey_year}",
        f"l{graduation_year}",
        f"a{years_after_degree}",
        definition,
    ]
    for name, value in filters:
        if value != "*":
            parts.append(f"{name}_{filename_slug(value)}")
    parts.append(f"split_{split_dimension}")
    return "__".join(parts) + ".csv"


def group_colors(groups):
    cmap = plt.get_cmap("tab20")
    return {group: cmap(index % 20) for index, group in enumerate(sorted(groups))}


def axis_group_label(value):
    value = shorten(str(value), width=34, placeholder="...")
    value = value.replace("-", "- ").replace(" e ", " e ")
    lines = wrap(value, width=12, break_long_words=False)
    return "\n".join(lines[:3])


def chart_width(item_count):
    return FIGURE_WIDTH


def make_boxplot(
    data: pd.DataFrame,
    years_after_degree: int,
    output_path: Path,
    university="*",
    disciplinary_group="*",
    course_type="*",
) -> None:
    plot_data = data.dropna(subset=["net_monthly_salary", "disciplinary_group"]).copy()
    if plot_data.empty:
        raise ValueError(f"No salary data available for annolau={years_after_degree}")

    order = (
        plot_data.groupby("disciplinary_group")["net_monthly_salary"]
        .median()
        .sort_values()
        .index
    )
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))
    values_by_group = [
        plot_data.loc[plot_data["disciplinary_group"] == group, "net_monthly_salary"].tolist()
        for group in order
    ]
    positions = list(range(1, len(order) + 1))
    ax.boxplot(
        values_by_group,
        positions=positions,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "#d9d9d9", "edgecolor": "#555555", "linewidth": 1.3},
        medianprops={"color": "#777777", "linewidth": 2.4},
        whiskerprops={"color": "#555555", "linewidth": 1.2},
        capprops={"color": "#555555", "linewidth": 1.2},
    )
    colors = group_colors(order)
    for index, group in enumerate(order, start=1):
        values = plot_data.loc[plot_data["disciplinary_group"] == group, "net_monthly_salary"].tolist()
        offsets = [((point_index % 9) - 4) * 0.025 for point_index, _ in enumerate(values)]
        x_values = [index + offset for offset in offsets]
        ax.scatter(x_values, values, s=26, alpha=0.72, color=colors[group])

    year = source_year(plot_data)
    graduation_year = year - years_after_degree if year else ""
    selected_filters = filter_label(university, disciplinary_group, course_type)
    fig.suptitle(
        chart_title(
            first_line="Distribuzione della retribuzione per gruppo disciplinare",
            years_after_degree=years_after_degree,
            graduation_year=graduation_year,
            definition=selected_definition(plot_data),
            extra_detail="box: distribuzione per ateneo; punti: atenei",
            filters=selected_filters,
        ),
        x=0.5,
        y=0.98,
        color=TABLEAU_RED,
        fontsize=TITLE_FONT_SIZE,
        linespacing=1.35,
    )
    ax.set_xlabel("")
    ax.set_ylabel("Retribuzione mensile netta", fontsize=AXIS_LABEL_FONT_SIZE)
    ax.set_xticks(positions)
    label_rotation = 32 if len(order) > 8 else 0
    label_alignment = "right" if label_rotation else "center"
    ax.set_xticklabels(
        [axis_group_label(group) for group in order],
        rotation=label_rotation,
        ha=label_alignment,
        rotation_mode="anchor",
        fontsize=X_TICK_FONT_SIZE,
    )
    ax.tick_params(axis="y", labelsize=TICK_FONT_SIZE)
    ax.grid(axis="y", alpha=0.2)
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=colors[group], markersize=8)
        for group in order
    ]
    ax.legend(
        handles,
        order,
        title="Legenda",
        bbox_to_anchor=(1.005, 1),
        loc="upper left",
        frameon=False,
        fontsize=LEGEND_FONT_SIZE,
        title_fontsize=LEGEND_TITLE_FONT_SIZE,
    )
    add_source_footer(year, years_after_degree, graduation_year)
    fig.subplots_adjust(left=0.065, right=0.79, top=0.84, bottom=0.23)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close()


def scatter_aggregate(data: pd.DataFrame, split_dimension="disciplinary_group") -> pd.DataFrame:
    clean = data.dropna(
        subset=["net_monthly_salary", "employment_rate", "graduates", "disciplinary_group"]
    ).copy()
    if split_dimension == "degree_class":
        if "degree_class" not in clean.columns:
            return pd.DataFrame()
        clean = clean[clean["degree_class"].fillna("*").astype(str) != "*"]
        if clean.empty:
            return pd.DataFrame()
        grouped = (
            clean.groupby(["degree_class", "disciplinary_group"], as_index=False)
            .agg(
                net_monthly_salary=("net_monthly_salary", "mean"),
                employment_rate=("employment_rate", "mean"),
                graduates=("graduates", "sum"),
            )
            .sort_values("net_monthly_salary")
        )
        grouped["point_label"] = grouped["degree_class"].map(degree_class_short_label)
        grouped["color_group"] = grouped["disciplinary_group"]
        return grouped

    if "degree_class" in clean.columns:
        clean = clean[clean["degree_class"].fillna("*").astype(str) == "*"]
    preferred = clean
    if {"university", "course_type"}.issubset(clean.columns):
        total_rows = clean[(clean["university"] == "*") & (clean["course_type"] == "*")]
        if not total_rows.empty:
            preferred = total_rows
        else:
            university_totals = clean[clean["university"] == "*"]
            course_totals = clean[clean["course_type"] == "*"]
            if not university_totals.empty:
                preferred = university_totals
            elif not course_totals.empty:
                preferred = course_totals

    grouped = (
        preferred.groupby("disciplinary_group", as_index=False)
        .agg(
            net_monthly_salary=("net_monthly_salary", "mean"),
            employment_rate=("employment_rate", "mean"),
            graduates=("graduates", "sum"),
        )
        .sort_values("net_monthly_salary")
    )
    grouped["point_label"] = grouped["disciplinary_group"].map(group_short_label)
    grouped["color_group"] = grouped["disciplinary_group"]
    return grouped


def make_scatterplot(
    data: pd.DataFrame,
    years_after_degree: int,
    output_path: Path,
    university="*",
    disciplinary_group="*",
    course_type="*",
    split_dimension="disciplinary_group",
) -> pd.DataFrame:
    aggregate = scatter_aggregate(data, split_dimension=split_dimension)
    if aggregate.empty:
        raise ValueError(f"No scatter data available for annolau={years_after_degree}")

    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_HEIGHT))
    size_values = aggregate["graduates"].clip(lower=1)
    sizes = 120 + (size_values / size_values.max()) * 950
    colors = group_colors(aggregate["color_group"])
    year = source_year(data)
    ax.scatter(
        aggregate["net_monthly_salary"],
        aggregate["employment_rate"],
        s=sizes,
        c=[colors[group] for group in aggregate["color_group"]],
        alpha=0.82,
        edgecolor="white",
        linewidth=1,
    )
    ax.margins(x=0.1, y=0.08)
    label_points = split_dimension == "disciplinary_group" or len(aggregate) <= 30
    if label_points:
        x_threshold = aggregate["net_monthly_salary"].quantile(0.8)
        x_range = aggregate["net_monthly_salary"].max() - aggregate["net_monthly_salary"].min()
        y_range = aggregate["employment_rate"].max() - aggregate["employment_rate"].min()
        x_offset = max(x_range * 0.008, 2)
        y_offset = max(y_range * 0.008, 0.08)
        texts = []
        for _, row in aggregate.iterrows():
            label_to_left = row["net_monthly_salary"] >= x_threshold
            label_x = row["net_monthly_salary"] - x_offset if label_to_left else row["net_monthly_salary"] + x_offset
            label_y = row["employment_rate"] + y_offset
            text = ax.text(
                label_x,
                label_y,
                shorten(str(row["point_label"]), width=36, placeholder="..."),
                ha="right" if label_to_left else "left",
                va="center",
                fontsize=POINT_LABEL_FONT_SIZE,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 2},
                zorder=5,
            )
            texts.append(text)
        if adjust_text is not None and texts:
            adjust_text(
                texts,
                x=aggregate["net_monthly_salary"].tolist(),
                y=aggregate["employment_rate"].tolist(),
                ax=ax,
                expand=(1.22, 1.45),
                force_text=(0.25, 0.45),
                force_static=(0.16, 0.24),
                max_move=(32, 24),
                min_arrow_len=5,
                time_lim=2,
                arrowprops={"arrowstyle": "-", "color": "#666666", "lw": 0.5, "alpha": 0.45},
            )
    graduation_year = year - years_after_degree if year else ""
    selected_filters = filter_label(university, disciplinary_group, course_type)
    split_label = split_dimension_label(split_dimension)
    first_line = f"Occupazione e retribuzione per {split_label}"
    extra_detail = "punti: gruppi disciplinari; bolle: laureati"
    if split_dimension == "degree_class":
        extra_detail = "punti: classi di laurea; bolle: laureati"
        if aggregate["color_group"].dropna().nunique() > 1:
            extra_detail += "; colore: gruppo disciplinare"
    fig.suptitle(
        chart_title(
            first_line=first_line,
            years_after_degree=years_after_degree,
            graduation_year=graduation_year,
            definition=selected_definition(data),
            extra_detail=extra_detail,
            filters=selected_filters,
        ),
        x=0.5,
        y=0.98,
        color=TABLEAU_RED,
        fontsize=TITLE_FONT_SIZE,
        linespacing=1.35,
    )
    ax.set_xlabel("Retribuzione mensile netta", fontsize=AXIS_LABEL_FONT_SIZE)
    ax.set_ylabel("Tasso di occupazione", fontsize=AXIS_LABEL_FONT_SIZE)
    ax.tick_params(axis="both", labelsize=TICK_FONT_SIZE)
    ax.grid(alpha=0.2)
    legend_groups = sorted(aggregate["color_group"].dropna().unique())
    handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=colors[group], markersize=8)
        for group in legend_groups
    ]
    if len(legend_groups) > 1:
        ax.legend(
            handles,
            legend_groups,
            title="Legenda",
            bbox_to_anchor=(1.005, 1),
            loc="upper left",
            frameon=False,
            fontsize=LEGEND_FONT_SIZE,
            title_fontsize=LEGEND_TITLE_FONT_SIZE,
        )
    add_source_footer(year, years_after_degree, graduation_year)
    right_margin = 0.94 if len(legend_groups) <= 1 else 0.79
    fig.subplots_adjust(left=0.08, right=right_margin, top=0.84, bottom=0.16)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close()
    return aggregate
