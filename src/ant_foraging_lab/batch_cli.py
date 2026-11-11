from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from ._version import MODEL_VERSION, TRACE_SCHEMA_VERSION
from .analysis import summarize_batch, write_comparison_svg, write_summary_csv
from .batch import run_batch, write_batch_csv
from .scenarios import no_recruitment_three_feeder, three_feeder_scenario


def _parse_seeds(value: str) -> tuple[int, ...]:
    text = value.strip()
    if ':' in text:
        parts = text.split(':')
        if len(parts) not in (2, 3):
            raise argparse.ArgumentTypeError('seed range must be START:STOP[:STEP]')
        try:
            numbers = [int(part) for part in parts]
            seeds = tuple(range(*numbers))
        except ValueError as exc:
            raise argparse.ArgumentTypeError('seeds must be integers') from exc
    else:
        try:
            seeds = tuple(int(part.strip()) for part in text.split(',') if part.strip())
        except ValueError as exc:
            raise argparse.ArgumentTypeError('seeds must be comma-separated integers') from exc
    if not seeds:
        raise argparse.ArgumentTypeError('at least one seed is required')
    if len(set(seeds)) != len(seeds):
        raise argparse.ArgumentTypeError('seeds must be unique')
    return seeds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='ant-foraging-lab-batch',
        description='Run paired multi-seed recruitment and no-recruitment experiments.',
    )
    parser.add_argument(
        '--seeds',
        type=_parse_seeds,
        default=_parse_seeds('0:30'),
        help='Comma-separated seeds or a Python-style START:STOP[:STEP] range.',
    )
    parser.add_argument('--max-steps', type=int, default=2_000)
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('results') / 'recruitment-comparison',
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_steps < 1:
        raise SystemExit('--max-steps must be at least 1')

    scenarios = {
        'nest_recruitment': three_feeder_scenario,
        'no_recruitment': no_recruitment_three_feeder,
    }
    records = run_batch(
        scenarios=scenarios,
        seeds=args.seeds,
        max_steps=args.max_steps,
    )
    summaries = summarize_batch(records)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_names = ('runs.csv', 'summary.csv', 'comparison.svg')
    write_batch_csv(records, output_dir / output_names[0])
    write_summary_csv(summaries, output_dir / output_names[1])
    write_comparison_svg(summaries, output_dir / output_names[2])

    manifest = {
        'schema_version': TRACE_SCHEMA_VERSION,
        'model_version': MODEL_VERSION,
        'scenarios': list(scenarios),
        'seeds': list(args.seeds),
        'max_steps': args.max_steps,
        'run_count': len(records),
        'outputs': list(output_names),
        'sha256': {
            name: sha256((output_dir / name).read_bytes()).hexdigest()
            for name in output_names
        },
    }
    (output_dir / 'manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n',
        encoding='utf-8',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
