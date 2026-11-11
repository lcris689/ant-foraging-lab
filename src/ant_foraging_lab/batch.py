from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from platform import python_version

from ._version import MODEL_VERSION, TRACE_SCHEMA_VERSION
from .model import RunResult, Simulation, SimulationConfig

ScenarioFactory = Callable[[int, int], SimulationConfig]


@dataclass(frozen=True)
class BatchRunRecord:
    """One reproducible simulation outcome and its complete configuration."""

    scenario: str
    seed: int
    config: SimulationConfig
    result: RunResult
    schema_version: int = TRACE_SCHEMA_VERSION
    model_version: str = MODEL_VERSION
    rng_family: str = 'python.random.Random'
    python_version: str = python_version()

    @property
    def reason(self) -> str:
        return self.result.reason.value

    def to_row(self) -> dict[str, str | int | float]:
        row: dict[str, str | int | float] = {
            'schema_version': self.schema_version,
            'model_version': self.model_version,
            'python_version': self.python_version,
            'rng_family': self.rng_family,
            'scenario': self.scenario,
            'seed': self.seed,
            'grid_size': self.config.grid_size,
            'nest_x': self.config.nest.x,
            'nest_y': self.config.nest.y,
            'ant_count': self.config.ant_count,
            'max_steps': self.config.max_steps,
            'termination_policy': self.config.termination_policy.value,
            'steps': self.result.steps,
            'reason': self.reason,
            'nest_food': self.result.nest_food,
            'carried_food': self.result.carried_food,
            'commitment_uncommitted': self.result.commitment_counts[None],
        }
        for feeder in self.config.feeders:
            prefix = f'feeder_{feeder.feeder_id}'
            row[f'{prefix}_x'] = feeder.position.x
            row[f'{prefix}_y'] = feeder.position.y
            row[f'{prefix}_quality'] = feeder.quality
            row[f'{prefix}_recruitment_rate'] = feeder.recruitment_rate
            row[f'{prefix}_attrition_rate'] = feeder.attrition_rate
            row[f'{prefix}_initial_food'] = feeder.food
            row[f'{prefix}_remaining'] = self.result.feeder_food[feeder.feeder_id]
            row[f'commitment_{feeder.feeder_id}'] = self.result.commitment_counts[
                feeder.feeder_id
            ]
        return row


def run_batch(
    *,
    scenarios: Mapping[str, ScenarioFactory],
    seeds: Sequence[int],
    max_steps: int,
) -> tuple[BatchRunRecord, ...]:
    """Run each named scenario over the same ordered seed schedule."""
    if not scenarios:
        raise ValueError('at least one scenario is required')
    if not seeds:
        raise ValueError('at least one seed is required')
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError('max_steps must be a positive integer')

    records = []
    for scenario_name, factory in scenarios.items():
        if not isinstance(scenario_name, str) or not scenario_name.strip():
            raise ValueError('scenario names must be non-empty strings')
        for seed in seeds:
            if type(seed) is not int:
                raise TypeError('batch seeds must be integers')
            config = factory(seed=seed, max_steps=max_steps)
            if config.seed != seed:
                raise ValueError(
                    f'scenario {scenario_name!r} did not preserve seed {seed}'
                )
            if config.max_steps != max_steps:
                raise ValueError(
                    f'scenario {scenario_name!r} did not preserve max_steps '
                    f'{max_steps}'
                )
            records.append(
                BatchRunRecord(
                    scenario=scenario_name,
                    seed=seed,
                    config=config,
                    result=Simulation(config).run(),
                )
            )
    return tuple(records)


def write_batch_csv(
    records: Iterable[BatchRunRecord],
    output_path: str | Path,
) -> Path:
    """Write one flat, analysis-ready CSV row per simulation run."""
    rows = [record.to_row() for record in records]
    if not rows:
        raise ValueError('cannot write an empty batch')

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction='raise')
        writer.writeheader()
        writer.writerows(rows)
    return path
