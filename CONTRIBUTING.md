# Contributing

Contributions should preserve the project's reproducibility and scientific-scope boundaries.

## Set up the repository

Requirements: Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check src tests
```

Run the browser interface with:

```bash
uv run ant-foraging-lab-web
```

## Engineering expectations

- Add a failing test before changing model behavior.
- Keep randomness model-owned or explicitly injected.
- Record the seed that actually generated each result.
- Keep every experiment bounded by an absolute step limit.
- Keep model state independent from API, visualization, and plotting code.
- Preserve food conservation, ant count, grid membership, and valid commitments.
- Treat recruitment and attrition as synchronous state transitions unless a separately named model defines another contract.

## Scientific writing

- Describe the project as a stochastic spatial agent-based simulation.
- Separate observations from hypotheses and planned work.
- Do not claim biological fidelity beyond the documented abstractions.
- Do not call a feature genetic or evolutionary without an explicit population, genome, fitness function, selection, recombination, mutation, and generations.
- Preserve attribution to the research that motivated the model.

## Pull-request checklist

- [ ] Behavioral changes have regression tests.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check src tests` passes.
- [ ] New experiment output records its seed and termination reason.
- [ ] Documentation agrees with code semantics.
- [ ] Generated artifacts and private source records are excluded.

## Publication safety

Do not add private archives, document metadata, personal identifiers, credentials, or source material that has not been reviewed for redistribution. Generate new plots, tables, and explanations directly from reproducible code and exported experiment data.
