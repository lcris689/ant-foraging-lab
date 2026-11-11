from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from statistics import mean, median, stdev

from .batch import BatchRunRecord


@dataclass(frozen=True)
class ScenarioSummary:
    scenario: str
    run_count: int
    nest_food_mean: float
    nest_food_median: float
    nest_food_stddev: float
    nest_food_min: int
    nest_food_max: int
    steps_mean: float
    censored_runs: int


def summarize_batch(records: tuple[BatchRunRecord, ...]) -> tuple[ScenarioSummary, ...]:
    """Summarize outcome location and spread without inferential claims."""
    grouped: dict[str, list[BatchRunRecord]] = defaultdict(list)
    order: list[str] = []
    for record in records:
        if record.scenario not in grouped:
            order.append(record.scenario)
        grouped[record.scenario].append(record)
    if not order:
        raise ValueError('cannot summarize an empty batch')

    summaries = []
    for scenario in order:
        scenario_records = grouped[scenario]
        nest_food = [record.result.nest_food for record in scenario_records]
        steps = [record.result.steps for record in scenario_records]
        summaries.append(
            ScenarioSummary(
                scenario=scenario,
                run_count=len(scenario_records),
                nest_food_mean=mean(nest_food),
                nest_food_median=median(nest_food),
                nest_food_stddev=stdev(nest_food) if len(nest_food) > 1 else 0.0,
                nest_food_min=min(nest_food),
                nest_food_max=max(nest_food),
                steps_mean=mean(steps),
                censored_runs=sum(
                    record.reason == 'max_steps_censored'
                    for record in scenario_records
                ),
            )
        )
    return tuple(summaries)


def write_summary_csv(
    summaries: tuple[ScenarioSummary, ...],
    output_path: str | Path,
) -> Path:
    if not summaries:
        raise ValueError('cannot write an empty summary')
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(summaries[0]))
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(summary) for summary in summaries)
    return path


def write_comparison_svg(
    summaries: tuple[ScenarioSummary, ...],
    output_path: str | Path,
) -> Path:
    """Generate a dependency-free bar chart of mean delivery with SD whiskers."""
    if not summaries:
        raise ValueError('cannot graph an empty summary')

    width = 900
    height = 560
    left = 90
    right = 40
    top = 80
    bottom = 130
    plot_width = width - left - right
    plot_height = height - top - bottom
    upper_values = [
        summary.nest_food_mean + summary.nest_food_stddev for summary in summaries
    ]
    y_max = max(max(upper_values), 1.0) * 1.1
    slot = plot_width / len(summaries)
    bar_width = min(120.0, slot * 0.55)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Mean food delivered to the nest</title>',
        '<desc id="desc">Scenario means with one standard deviation error bars across the recorded seed schedule.</desc>',
        '<rect width="100%" height="100%" fill="#f6efe4"/>',
        '<text x="45" y="38" font-family="system-ui, sans-serif" font-size="24" font-weight="700" fill="#231f20">Mean food delivered to the nest</text>',
        '<text x="45" y="62" font-family="system-ui, sans-serif" font-size="13" fill="#5a514a">Bars show the mean; whiskers show ±1 sample standard deviation.</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#514941" stroke-width="2"/>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#514941" stroke-width="2"/>',
    ]

    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_height - plot_height * tick / 5
        lines.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#d8ccc0" stroke-width="1"/>',
                f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="system-ui, sans-serif" font-size="12" fill="#5a514a">{value:.1f}</text>',
            ]
        )

    colors = ('#c65d3b', '#2f6f66', '#6d5b9a', '#ad7b2f')
    baseline_y = top + plot_height
    for index, summary in enumerate(summaries):
        center = left + slot * (index + 0.5)
        bar_height = plot_height * summary.nest_food_mean / y_max
        bar_y = baseline_y - bar_height
        error = plot_height * summary.nest_food_stddev / y_max
        color = colors[index % len(colors)]
        label = escape(summary.scenario)
        lines.extend(
            [
                f'<rect x="{center - bar_width / 2:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="4" fill="{color}"/>',
                f'<line x1="{center:.2f}" y1="{bar_y - error:.2f}" x2="{center:.2f}" y2="{bar_y + error:.2f}" stroke="#231f20" stroke-width="2"/>',
                f'<line x1="{center - 10:.2f}" y1="{bar_y - error:.2f}" x2="{center + 10:.2f}" y2="{bar_y - error:.2f}" stroke="#231f20" stroke-width="2"/>',
                f'<line x1="{center - 10:.2f}" y1="{bar_y + error:.2f}" x2="{center + 10:.2f}" y2="{bar_y + error:.2f}" stroke="#231f20" stroke-width="2"/>',
                f'<text x="{center:.2f}" y="{bar_y - error - 10:.2f}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#231f20">{summary.nest_food_mean:.1f}</text>',
                f'<text x="{center:.2f}" y="{baseline_y + 28}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" fill="#231f20">{label}</text>',
                f'<text x="{center:.2f}" y="{baseline_y + 48}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="11" fill="#5a514a">n={summary.run_count}</text>',
            ]
        )

    lines.append('</svg>')
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path
