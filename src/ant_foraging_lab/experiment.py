from __future__ import annotations

from dataclasses import asdict, dataclass

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
class ExperimentTrace:
    config: SimulationConfig
    frame_stride: int
    frames: tuple[ExperimentFrame, ...]
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


def run_experiment(
    config: SimulationConfig,
    *,
    frame_stride: int = 10,
) -> ExperimentTrace:
    if frame_stride < 1:
        raise ValueError('frame_stride must be at least 1')

    simulation = Simulation(config)
    frames = [_capture(simulation)]
    reason = simulation.termination_reason()

    while reason is None:
        reason = simulation.step()
        if simulation.steps % frame_stride == 0 or reason is not None:
            frames.append(_capture(simulation))

    result = simulation.run()
    if frames[-1].step != result.steps:
        frames.append(_capture(simulation))

    return ExperimentTrace(
        config=config,
        frame_stride=frame_stride,
        frames=tuple(frames),
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