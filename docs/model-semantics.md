# Model Semantics

This document defines the authoritative timestep behavior of the implementation in `src/ant_foraging_lab`.

## Recruitment decision

Each ant that was committed at the start of the timestep may make at most one recruitment attempt after it is at the nest without carried food:

1. Find ants at the nest that are uncommitted at the start of the social-update phase.
2. Uniformly select one eligible nestmate.
3. Draw one Bernoulli event using the committed feeder's recruitment rate.
4. If it succeeds, queue a proposal for that nestmate.

The implementation does not retry against additional eligible nestmates after a failed attempt. Therefore the configured recruitment rate remains the per-recruiter probability described in the original report instead of increasing with the number of available nestmates.

Ants occupying the same nest cell are eligible to interact; geometric adjacency away from the nest does not trigger recruitment. A returning ant that reaches the nest while carrying food must deposit it before becoming eligible to recruit. If successful recruiters from different feeders target the same ant, one of the successful feeder proposals is selected with the simulation's seeded random-number generator.

## Synchronous state updates

Recruitment and attrition decisions are calculated before either type of state change is applied. This prevents a recruited ant from recruiting another ant in the same timestep.

Only ants that were committed at the start of the timestep are eligible for attrition. An ant newly committed through discovery or recruitment receives at least one full timestep in that state before an attrition decision.

An established recruiter may recruit and then experience attrition in the same timestep. Both decisions are based on its commitment at the start of the phase.

## Movement and resource order

For each timestep:

1. Record which ants begin the timestep committed.
2. Process movement in stable ant-ID order.
3. Let returning ants move toward the nest or deposit carried food.
4. Let committed ants move toward their feeder and collect food when present.
5. Let uncommitted ants choose uniformly from valid neighboring grid positions; on a 1 × 1 grid they remain in place.
6. Resolve feeder discovery and collection for uncommitted ants.
7. Let established committed ants at the nest without carried food attempt recruitment, then resolve recruitment and attrition synchronously.
8. Check model invariants.

Food pickup is spatially local: a committed ant may decrement a feeder's inventory only after its position equals that feeder's position.

Stable ant-ID order makes seeded runs reproducible even if the internal ant list is reordered. Ant IDs still define the deterministic order in which random draws are assigned.

This is a deterministic scheduling convention, not proof that resource access is unbiased. Lower ant IDs currently receive earlier random draws and first access to a feeder when multiple ants encounter its last food units during one timestep. Staged resource contention remains a candidate improvement.

Custom initial ant collections may set positions and commitments, but cannot begin with carried food because the public configuration currently defines all initial food as feeder inventory. Snapshot restoration will require a separate initial-state object that records feeder, carried, and nest food together.

## Random-seed provenance

Normal simulations own a `random.Random(config.seed)` instance, and that seed is recorded in `RunResult`. A custom random source may be injected for controlled tests. Calling `run()` with a custom source requires an explicit `rng_seed`, preventing the configuration seed from being mislabeled as the source of unrelated random draws.

## Termination

Every run has a required positive `max_steps` value. Fixed-step termination is the default so experiments being compared use the same horizon.

Optional policies are explicit:

- `FIXED_STEPS` — always run to `max_steps` and report `FIXED_HORIZON_COMPLETE`.
- `FIRST_FEEDER_DEPLETED` — stop after the first timestep that leaves any feeder empty.
- `ALL_FEEDERS_DEPLETED` — stop after the first timestep that leaves every feeder empty.

If a depletion-policy run reaches the absolute bound before its depletion condition, it reports `MAX_STEPS_CENSORED`. The result therefore distinguishes planned fixed-horizon completion from a depletion experiment censored by its safety bound.

`max_steps` is an absolute simulation bound rather than an additional budget for each call to `run()`. Repeating `run()` after termination returns the same final result without advancing the model. A depletion policy also terminates at step zero if its depletion condition is already true initially.

Direct calls to `step()` enforce the same bound and reject attempts to advance a simulation that has already reached a configured depletion condition.

## Recorded provenance

Serialized experiment traces include a trace-schema version, model/package version, scenario label, Python version, random-generator family, and the seed that generated the run. Deterministic replay is scoped to matching recorded provenance; a seed and configuration alone do not promise identical behavior across model releases.

## Invariants checked after every step

- Ant IDs remain unique.
- Every ant position is inside the grid.
- Every commitment references a configured feeder.
- Feeder inventories never become negative.
- Food in the nest, carried by ants, and remaining in feeders equals the initial food total.

## Remaining scientific decisions

- Whether deterministic Manhattan movement is an acceptable abstraction.
- Which fixed horizon or equilibrium measure is appropriate for each experiment.
- How the spatial implementation should be compared quantitatively with the motivating ODE.
