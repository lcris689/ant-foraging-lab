# Interactive Web Lab

The web lab is a local interface over the tested Python simulation engine. The browser does not reimplement movement, recruitment, attrition, or food accounting.

## Start the application

```bash
uv sync
uv run ant-foraging-lab-web
```

Open <http://127.0.0.1:8000>. API schema documentation is available at <http://127.0.0.1:8000/docs>.

## Experiment controls

The preset selector provides three starting points:

- **Guided mechanism demo** uses a compact 40 × 40 grid, nearby feeders, 120 ants, and a 400-step horizon so discovery, recruitment, and delivery are usually visible. It is a teaching configuration, not comparative evidence.
- **Reference experiment** restores the published 100 × 100 configuration. Exact-cell discovery is intentionally sparse and should be interpreted across seed sets.
- **Guided demo — recruitment off** changes only the guided demo's recruitment probabilities to zero, enabling a matched same-seed visual comparison.

Editing any field marks the configuration as **Custom settings**. Directional effects below are typical rather than guaranteed because the model is stochastic.

| Control | Meaning | Typical effect of increasing or changing it |
| --- | --- | --- |
| Seed | Initializes the model-owned pseudorandom generator | Changes individual paths and outcomes while leaving the intended scenario unchanged; it is for replay, not tuning |
| Ants | Number of agents in the colony | More ants usually create more encounters and deliveries, with higher compute and trace cost |
| Grid size | Width and height of the square environment | A larger search area usually makes exact feeder discovery slower and sparser |
| Max steps | Absolute upper bound for the simulation | A longer horizon allows more discovery and transport, with higher compute cost |
| Sample every | Steps between recorded animation frames | A smaller interval creates smoother replay and larger responses; it does not change model decisions |
| Stop rule | Fixed duration, first feeder empty, or all feeders empty | Changes the observation endpoint and can make final outcomes unsuitable for direct comparison |
| Nest X/Y | Nest location inside the grid | Changes every nest-to-feeder travel distance and the colony's common starting point |
| Feeder X/Y | Food-source location inside the grid | A feeder nearer the nest is usually encountered and serviced sooner |
| Quality | Probability that an uncommitted ant commits after reaching the feeder | A higher value makes an encountered feeder more likely to establish commitment |
| Recruitment | Probability for one eligible nest-based attempt per established recruiter | A higher value usually spreads an established commitment faster when recruiter and recruit meet at the nest |
| Attrition | Per-step probability that a committed ant becomes uncommitted | A higher value makes allocations less persistent and can reduce sustained transport |
| Food | Initial integer inventory at the feeder | More food keeps the source available longer but does not make it easier to discover |

Positions must be inside the configured grid. Probabilities are bounded to `[0, 1]`; food, colony size, and step counts must be positive.

## Visualization

The colony panel samples a completed run and replays it without changing the underlying result.

The page waits for an explicit **Run experiment** action. Loading or refreshing the page never starts simulation work automatically.

- Squares mark the nest.
- Diamonds mark feeders.
- Ant color identifies commitment.
- A contrasting ring identifies ants currently carrying food.
- The timeline moves between sampled frames.
- Allocation bars and food measurements update with the selected frame.
- The significant-events log reveals feeder discoveries, the first delivery, the first successful nest recruitment, delivery milestones, feeder depletion, and run completion as replay reaches each event.

After an explicit run request completes, replay starts at step zero so users can watch the behavior develop instead of seeing only the final state. Reduced-motion preferences disable automatic playback. A lower sampling interval produces smoother replay and larger JSON exports. Sampling does not alter simulation decisions, and event detection does not consume random draws.

## Data collection and privacy

The current application is deliberately local-first:

- Up to 50 run summaries are stored in browser `localStorage`.
- **Download run JSON** exports the complete current configuration, sampled frames, and result.
- **Download history CSV** exports summary rows for runs stored in that browser.
- No experiment is persisted by the FastAPI server.
- No account, personal identifier, cookie-based analytics, or external telemetry is used.

Clearing browser storage or selecting **Clear history** removes locally retained summaries. This design supports reproducible local and classroom experiments without introducing a public data-submission service or its privacy and abuse-prevention obligations.

## HTTP API

### `GET /api/health`

Returns application availability:

```json
{"status": "ok"}
```

### `POST /api/runs`

Example request:

```json
{
  "seed": 689,
  "grid_size": 100,
  "nest": {"x": 50, "y": 50},
  "ant_count": 200,
  "max_steps": 1000,
  "frame_stride": 10,
  "termination_policy": "fixed_steps",
  "feeders": [
    {
      "feeder_id": "A",
      "position": {"x": 25, "y": 75},
      "quality": 0.75,
      "recruitment_rate": 0.75,
      "attrition_rate": 0.009,
      "food": 1000
    }
  ]
}
```

The response contains:

- `provenance`: trace schema, package version, model version, scenario label, Python version, and random-generator family;
- `config`: the validated configuration;
- `frame_stride`: the sampling interval;
- `frames`: sampled positions and aggregate measurements, including initial and final state;
- `events`: significant model events recorded at their exact simulation step, including events between sampled frames;
- `result`: seed, steps, termination reason, food inventory, and final commitments.

Input limits allow at most 500 ants, 5,000 steps, five feeders, a 150 × 150 grid, and 500 sampled frames per request. Independent server-side budgets additionally reject requests above 250,000 ant-steps or 50,000 sampled ant states.

## Hosting boundary

The development server binds to `127.0.0.1` by default. The portfolio should use a screenshot, generated comparison figure, or precomputed replay rather than expose `POST /api/runs` publicly.

Any future public execution service would still require rate limiting, request-size controls, concurrency limits, cancellable timeouts, monitoring, and an explicit data-retention policy. The local API's validation budgets are defense in depth, not a complete public-hosting security boundary.
