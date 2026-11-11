import csv
import hashlib
import json

from ant_foraging_lab.analysis import (
    summarize_batch,
    write_comparison_svg,
    write_summary_csv,
)
from ant_foraging_lab.batch import run_batch, write_batch_csv
from ant_foraging_lab.batch_cli import main as batch_main
from ant_foraging_lab.model import FeederConfig, Position, SimulationConfig
from ant_foraging_lab.scenarios import (
    no_recruitment_three_feeder,
    three_feeder_scenario,
)


def scenario(*, seed: int, max_steps: int, recruitment_rate: float) -> SimulationConfig:
    return SimulationConfig(
        grid_size=3,
        nest=Position(1, 1),
        feeders=(
            FeederConfig('A', Position(0, 0), 1.0, recruitment_rate, 0.0, 10),
        ),
        ant_count=4,
        max_steps=max_steps,
        seed=seed,
    )


def test_batch_runner_uses_the_same_seed_set_for_each_scenario():
    records = run_batch(
        scenarios={
            'recruitment': lambda seed, max_steps: scenario(
                seed=seed,
                max_steps=max_steps,
                recruitment_rate=1.0,
            ),
            'no_recruitment': lambda seed, max_steps: scenario(
                seed=seed,
                max_steps=max_steps,
                recruitment_rate=0.0,
            ),
        },
        seeds=(3, 7),
        max_steps=5,
    )

    assert [(record.scenario, record.seed) for record in records] == [
        ('recruitment', 3),
        ('recruitment', 7),
        ('no_recruitment', 3),
        ('no_recruitment', 7),
    ]
    assert all(record.model_version == '0.2.0' for record in records)
    assert all(record.reason == 'fixed_horizon_complete' for record in records)


def test_batch_csv_preserves_tidy_per_run_results(tmp_path):
    records = run_batch(
        scenarios={
            'no_recruitment': lambda seed, max_steps: scenario(
                seed=seed,
                max_steps=max_steps,
                recruitment_rate=0.0,
            ),
        },
        seeds=(11,),
        max_steps=4,
    )
    output = tmp_path / 'runs.csv'

    write_batch_csv(records, output)

    with output.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]['scenario'] == 'no_recruitment'
    assert rows[0]['seed'] == '11'
    assert rows[0]['model_version'] == '0.2.0'
    assert rows[0]['feeder_A_remaining']
    assert rows[0]['commitment_A']
    assert rows[0]['commitment_uncommitted']


def test_batch_analysis_writes_summary_and_generated_figure(tmp_path):
    records = run_batch(
        scenarios={
            'recruitment': lambda seed, max_steps: scenario(
                seed=seed,
                max_steps=max_steps,
                recruitment_rate=1.0,
            ),
            'no_recruitment': lambda seed, max_steps: scenario(
                seed=seed,
                max_steps=max_steps,
                recruitment_rate=0.0,
            ),
        },
        seeds=(3, 7),
        max_steps=5,
    )

    summaries = summarize_batch(records)
    summary_path = write_summary_csv(summaries, tmp_path / 'summary.csv')
    figure_path = write_comparison_svg(summaries, tmp_path / 'comparison.svg')

    assert [summary.scenario for summary in summaries] == [
        'recruitment',
        'no_recruitment',
    ]
    assert all(summary.run_count == 2 for summary in summaries)
    assert summary_path.read_text(encoding='utf-8').startswith('scenario,run_count')
    figure = figure_path.read_text(encoding='utf-8')
    assert figure.startswith('<svg')
    assert 'Mean food delivered to the nest' in figure
    assert 'recruitment' in figure


def test_no_recruitment_baseline_changes_only_recruitment_rates():
    treatment = three_feeder_scenario(seed=689, max_steps=50)
    baseline = no_recruitment_three_feeder(seed=689, max_steps=50)

    assert baseline.seed == treatment.seed
    assert baseline.max_steps == treatment.max_steps
    assert [feeder.recruitment_rate for feeder in baseline.feeders] == [0.0, 0.0, 0.0]
    assert [
        (feeder.feeder_id, feeder.position, feeder.quality, feeder.attrition_rate, feeder.food)
        for feeder in baseline.feeders
    ] == [
        (feeder.feeder_id, feeder.position, feeder.quality, feeder.attrition_rate, feeder.food)
        for feeder in treatment.feeders
    ]


def test_batch_cli_writes_a_reproducibility_bundle(tmp_path):
    exit_code = batch_main(
        [
            '--seeds',
            '3,7',
            '--max-steps',
            '2',
            '--output-dir',
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / 'runs.csv').is_file()
    assert (tmp_path / 'summary.csv').is_file()
    assert (tmp_path / 'comparison.svg').is_file()
    assert (tmp_path / 'manifest.json').is_file()

    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    for name in ('runs.csv', 'summary.csv', 'comparison.svg'):
        digest = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        assert manifest['sha256'][name] == digest
