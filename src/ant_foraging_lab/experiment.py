from __future__ import annotations

from dataclasses import asdict, dataclass
from platform import python_version

from ._version import MODEL_VERSION, TRACE_SCHEMA_VERSION, __version__
from .model import Position, RunResult, Simulation, SimulationConfig


@dataclass(frozen=True)
class AntSnapshot:
    ant_id: int
    position: Position
    commitment: str | None
    holding_food: bool


@dataclass(frozen=True)
class ExperimentFrame:
    step: int
    nest_food: int
    carried_food: int
    feeder_food: dict[str, int]
    commitment_counts: dict[str, int]
    ants: tuple[AntSnapshot, ...]


@dataclass(frozen=True)
class ExperimentProvenance:
    schema_version: int
    package_version: str
    model_version: str
    scenario_name: str
    rng_family: str
    python_version: str


@dataclass(frozen=True)
class ExperimentEvent:
    step: int
    kind: str
    title: str
    detail: str
    feeder_id: str | None = None
    value: int | None = None


@dataclass(frozen=True)
class ExperimentTrace:
    provenance: ExperimentProvenance
    config: SimulationConfig
    frame_stride: int
    frames: tuple[ExperimentFrame, ...]
    events: tuple[ExperimentEvent, ...]
    result: RunResult


def _commitment_counts(simulation: Simulation) -> dict[str, int]:
    counts = {'uncommitted': 0}
    counts.update({feeder_id: 0 for feeder_id in simulation.feeders})
    for ant in simulation.ants:
        key = ant.commitment if ant.commitment is not None else 'uncommitted'
        counts[key] += 1
    return counts


def _capture(simulation: Simulation) -> ExperimentFrame:
    return ExperimentFrame(
        step=simulation.steps,
        nest_food=simulation.nest_food,
        carried_food=sum(ant.holding_food for ant in simulation.ants),
        feeder_food=dict(simulation.feeder_food),
        commitment_counts=_commitment_counts(simulation),
        ants=tuple(
            AntSnapshot(
                ant_id=ant.ant_id,
                position=ant.position,
                commitment=ant.commitment,
                holding_food=ant.holding_food,
            )
            for ant in sorted(simulation.ants, key=lambda item: item.ant_id)
        ),
    )


def _step_events(
    simulation: Simulation,
    *,
    previous_nest_food: int,
    previous_feeder_food: dict[str, int],
    discovered_feeders: set[str],
    recruitment_recorded: bool,
    delivery_milestones: set[int],
) -> tuple[list[ExperimentEvent], bool]:
    events: list[ExperimentEvent] = []
    for _, feeder_id in simulation.last_discoveries:
        if feeder_id not in discovered_feeders:
            discovered_feeders.add(feeder_id)
            events.append(ExperimentEvent(
                step=simulation.steps,
                kind='feeder_discovered',
                title=f'Feeder {feeder_id} discovered',
                detail=(
                    f'An uncommitted ant reached feeder {feeder_id} '
                    'and committed to it.'
                ),
                feeder_id=feeder_id,
            ))

    if previous_nest_food == 0 and simulation.nest_food > 0:
        events.append(ExperimentEvent(
            step=simulation.steps,
            kind='first_delivery',
            title='First food delivered',
            detail='The colony delivered its first food to the nest.',
            value=simulation.nest_food,
        ))

    for milestone in (10, 50, 100, 250, 500, 1000):
        if (
            milestone not in delivery_milestones
            and previous_nest_food < milestone <= simulation.nest_food
        ):
            delivery_milestones.add(milestone)
            events.append(ExperimentEvent(
                step=simulation.steps,
                kind='delivery_milestone',
                title=f'{milestone:,} food delivered',
                detail=f'Nest deliveries reached {milestone:,} units.',
                value=milestone,
            ))

    if not recruitment_recorded and simulation.last_recruitments:
        _, feeder_id = simulation.last_recruitments[0]
        recruitment_recorded = True
        events.append(ExperimentEvent(
            step=simulation.steps,
            kind='first_recruitment',
            title='First successful recruitment',
            detail=(
                f'A feeder {feeder_id} recruiter committed '
                'an uncommitted ant at the nest.'
            ),
            feeder_id=feeder_id,
        ))

    for feeder_id in sorted(simulation.feeder_food):
        if previous_feeder_food[feeder_id] > 0 and simulation.feeder_food[feeder_id] == 0:
            events.append(ExperimentEvent(
                step=simulation.steps,
                kind='feeder_depleted',
                title=f'Feeder {feeder_id} depleted',
                detail=f'No food remains at feeder {feeder_id}.',
                feeder_id=feeder_id,
            ))

    return events, recruitment_recorded


def run_experiment(
    config: SimulationConfig,
    *,
    frame_stride: int = 10,
    scenario_name: str = 'custom',
) -> ExperimentTrace:
    if frame_stride < 1:
        raise ValueError('frame_stride must be at least 1')
    if not isinstance(scenario_name, str) or not scenario_name.strip():
        raise ValueError('scenario_name must be a non-empty string')

    simulation = Simulation(config)
    frames = [_capture(simulation)]
    events: list[ExperimentEvent] = []
    discovered_feeders: set[str] = set()
    recruitment_recorded = False
    delivery_milestones: set[int] = set()
    reason = simulation.termination_reason()

    while reason is None:
        previous_nest_food = simulation.nest_food
        previous_feeder_food = dict(simulation.feeder_food)
        reason = simulation.step()
        step_events, recruitment_recorded = _step_events(
            simulation,
            previous_nest_food=previous_nest_food,
            previous_feeder_food=previous_feeder_food,
            discovered_feeders=discovered_feeders,
            recruitment_recorded=recruitment_recorded,
            delivery_milestones=delivery_milestones,
        )
        events.extend(step_events)
        if simulation.steps % frame_stride == 0 or reason is not None:
            frames.append(_capture(simulation))

    result = simulation.run()
    if frames[-1].step != result.steps:
        frames.append(_capture(simulation))
    events.append(ExperimentEvent(
        step=result.steps,
        kind='run_complete',
        title='Run complete',
        detail=(
            f'The run ended after {result.steps:,} steps: '
            f'{result.reason.value.replace("_", " ")}.'
        ),
        value=result.nest_food,
    ))

    return ExperimentTrace(
        provenance=ExperimentProvenance(
            schema_version=TRACE_SCHEMA_VERSION,
            package_version=__version__,
            model_version=MODEL_VERSION,
            scenario_name=scenario_name,
            rng_family='python.random.Random',
            python_version=python_version(),
        ),
        config=config,
        frame_stride=frame_stride,
        frames=tuple(frames),
        events=tuple(events),
        result=result,
    )


def trace_to_dict(trace: ExperimentTrace) -> dict:
    data = asdict(trace)
    data['config']['termination_policy'] = trace.config.termination_policy.value
    data['result']['reason'] = trace.result.reason.value
    data['result']['commitment_counts'] = {
        ('uncommitted' if key is None else key): value
        for key, value in trace.result.commitment_counts.items()
    }
    return data