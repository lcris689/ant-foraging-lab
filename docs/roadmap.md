# Development Roadmap

## Phase 0 — Establish a safe publication boundary

- [x] Keep private source records and submission archives outside the public repository.
- [x] Remove excluded historical materials from reachable Git history.
- [x] Replace the historical author email in Git history with the GitHub noreply address.
- [x] Review reachable history for credentials, personal paths, and oversized artifacts.
- [x] License the independently authored active project under MIT.

## Phase 1 — Tested simulation core

- [x] Introduce dataclasses for positions, ants, feeders, and simulation configuration.
- [x] Inject a seeded random-number generator.
- [x] Use enums for finite termination policies and reasons while retaining feeder IDs as data.
- [x] Separate movement and synchronous social-update phases in the new model core.
- [x] Use snapshot/two-phase social updates so recruitment does not depend on ant list order.
- [x] Define and test exactly one recruitment decision per eligible recruiter per timestep.
- [x] Prevent newly committed ants from experiencing attrition in the same timestep.
- [x] Add maximum-step termination and structured termination reasons.
- [x] Add tests for grid boundaries, including 1 × 1 grids, food conservation, valid state transitions, recruitment, attrition, and feeder depletion.
- [x] Express compared treatments as named scenario factories.

## Phase 2 — Reproducible experiments

- [x] Add a command-line interface for seed schedule, run horizon, and output path.
- [x] Export each browser run with configuration, seed, duration, food delivered, and allocation metrics.
- [x] Add a batch-oriented tidy-data runner for multi-seed statistical experiments.
- [x] Add fixed-duration, first-depletion, and all-depleted experiment endpoints.
- [ ] Compare confidence-interval methods and document the selected approach.
- [ ] Treat feeder allocations as correlated compositional outcomes rather than unrelated percentages.
- [x] Add a matched no-recruitment baseline.
- [ ] Add a separately justified random-walk baseline.
- [ ] Compare symmetric feeder scenarios over many seeds and validate qualitative behavior against the motivating ODE.
- [ ] Benchmark runtime before optimizing.

## Phase 3 — Interactive visualization

- [x] Animate ants, nest, and feeders in a browser.
- [x] Show current state counts and feeder inventory in a focused lab interface.
- [x] Support browser-local run history plus JSON and CSV downloads.
- [x] Let a viewer replay any submitted seed and configuration.
- [ ] Plot best/average behavior across repeated seeded runs.
- [x] Capture an authentic screenshot from a completed seeded run.
- [ ] Record a concise demonstration for the portfolio.
- [x] Keep compute local and use screenshots or generated results for the public portfolio.

## Phase 4 — Genuine evolutionary extension

Choose one explicit genome and keep it separate from the historical model. Candidate genome parameters include exploration persistence, return-to-nest tendency, recruitment probability, attrition sensitivity, and feeder-quality weighting.

- [ ] Define the genome and allowable ranges.
- [ ] Define fitness across multiple environment seeds to prevent overfitting to one map.
- [ ] Implement population initialization, parent selection, crossover, mutation, and elitism.
- [ ] Record generation-level best, mean, and diversity metrics.
- [ ] Compare evolved strategies against random and hand-configured baselines on held-out environments.
- [ ] Test deterministic replay from both experiment seed and genome.
- [ ] Explain why the extension is a genetic algorithm and what remains biologically simplified.

## Phase 5 — Optional homelab experiment runner

Do not begin until the local implementation and homelab prerequisites are verified.

- [ ] Package simulations in a container.
- [ ] Queue batches of seeded experiments.
- [ ] Persist configurations and results without personal or network-sensitive data.
- [ ] Monitor worker runtime and failures.
- [ ] Document deployed versus planned infrastructure accurately.
