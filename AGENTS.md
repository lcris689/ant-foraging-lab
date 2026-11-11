# Ant Foraging Lab Agent Guide

## Purpose
Develop a reproducible agent-based ant-foraging simulation and, in a later phase, evaluate a genuine evolutionary-computation extension.

## Source of truth
- This Git repository is canonical.
- Original source records remain outside this repository and are not publication artifacts.
- Private source records and submission materials are intentionally excluded from this public project.

## Scientific accuracy
- Describe the current model as a stochastic spatial agent-based simulation based on collective foraging—not as a genetic algorithm.
- A feature may be called evolutionary or genetic only after it implements an explicit population, genome, fitness function, selection, crossover/recombination, mutation, and generations.
- Preserve the Shaffer, Sasaki, and Pratt research attribution that motivates the model.
- Separate observed results from hypotheses and planned experiments.

## Engineering workflow
1. Check Git status before editing and preserve unrelated work.
2. Use test-driven development for the new implementation.
3. Make randomness injectable and every experiment reproducible from a recorded seed.
4. Keep simulation state separate from plotting and UI code.
5. Add bounded termination conditions to every experiment.
6. Verify invariants such as ant count, grid membership, feeder inventory, and valid states.
7. Run `uv run pytest` before declaring code changes complete.

## Publication safety
- Do not publish personal identifiers, document metadata, private records, or restricted material.
- Do not claim biological fidelity beyond the simplified model.
