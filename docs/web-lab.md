# Interactive Web Lab

The web lab is a local interface over the tested Python simulation engine. The browser does not reimplement movement, recruitment, attrition, or food accounting.

## Start the application

```bash
uv sync
uv run ant-foraging-lab-web
```

Open <http://127.0.0.1:8000>. API schema documentation is available at <http://127.0.0.1:8000/docs>.

## Experiment controls

| Control | Meaning |
| --- | --- |
| Seed | Initializes the model-owned pseudorandom generator |
| Ants | Number of agents in the colony |
| Grid size | Width and height of the square spatial environment |
| Max steps | Absolute upper bound for the simulation |
| Sample every | Number of simulation steps between recorded animation frames |
| Stop rule | Fixed duration, first feeder empty, or all feeders empty |
| Nest X/Y | Nest location inside the grid |
| Feeder X/Y | Food-source location inside the grid |
| Quality | Probability that an uncommitted ant commits after encountering the feeder |
| Recruitment | Probability for one eligible nest-based recruitment opportunity per established recruiter after depositing carried food |
| Attrition | Probability that an established committed ant becomes uncommitted |
| Food | Initial integer inventory at the feeder |

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

A lower sampling interval produces smoother replay and larger JSON exports. Sampling does not alter simulation decisions.

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

- `provenance`: trace schema, model version, scenario label, Python version, and random-generator family;
- `config`: the validated configuration;
- `frame_stride`: the sampling interval;
- `frames`: sampled positions and aggregate measurements, including initial and final state;
- `result`: seed, steps, termination reason, food inventory, and final commitments.

Input limits allow at most 500 ants, 5,000 steps, five feeders, a 150 × 150 grid, and 500 sampled frames per request. Independent server-side budgets additionally reject requests above 250,000 ant-steps or 50,000 sampled ant states.

## Hosting boundary

The development server binds to `127.0.0.1` by default. The portfolio should use a screenshot, generated comparison figure, or precomputed replay rather than expose `POST /api/runs` publicly.

Any future public execution service would still require rate limiting, request-size controls, concurrency limits, cancellable timeouts, monitoring, and an explicit data-retention policy. The local API's validation budgets are defense in depth, not a complete public-hosting security boundary.
