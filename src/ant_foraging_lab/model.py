from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol, TypeVar

T = TypeVar('T')


def _require_int(name: str, value: object) -> None:
    if type(value) is not int:
        raise TypeError(f'{name} must be an integer')


def _require_probability(name: str, value: object) -> None:
    if type(value) not in (int, float):
        raise TypeError(f'{name} must be a finite number')
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f'{name} must be between 0 and 1')


class RandomSource(Protocol):
    def random(self) -> float: ...

    def choice(self, values: Sequence[T]) -> T: ...


class TerminationPolicy(Enum):
    FIXED_STEPS = 'fixed_steps'
    FIRST_FEEDER_DEPLETED = 'first_feeder_depleted'
    ALL_FEEDERS_DEPLETED = 'all_feeders_depleted'


class TerminationReason(Enum):
    FIXED_HORIZON_COMPLETE = 'fixed_horizon_complete'
    MAX_STEPS_CENSORED = 'max_steps_censored'
    FIRST_FEEDER_DEPLETED = 'first_feeder_depleted'
    ALL_FEEDERS_DEPLETED = 'all_feeders_depleted'


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError('position coordinates must be integers')

    def is_adjacent_to(self, other: Position) -> bool:
        return abs(self.x - other.x) + abs(self.y - other.y) == 1


@dataclass(frozen=True)
class FeederConfig:
    feeder_id: str
    position: Position
    quality: float
    recruitment_rate: float
    attrition_rate: float
    food: int

    def __post_init__(self) -> None:
        if not isinstance(self.feeder_id, str):
            raise TypeError('feeder_id must be a string')
        if not self.feeder_id.strip():
            raise ValueError('feeder_id must not be empty')
        for field_name in ('quality', 'recruitment_rate', 'attrition_rate'):
            _require_probability(field_name, getattr(self, field_name))
        _require_int('food', self.food)
        if self.food < 0:
            raise ValueError('food must not be negative')


@dataclass(frozen=True)
class SimulationConfig:
    grid_size: int
    nest: Position
    feeders: tuple[FeederConfig, ...]
    ant_count: int
    max_steps: int
    seed: int
    termination_policy: TerminationPolicy = TerminationPolicy.FIXED_STEPS

    def __post_init__(self) -> None:
        for field_name in ('grid_size', 'ant_count', 'max_steps', 'seed'):
            _require_int(field_name, getattr(self, field_name))
        if not isinstance(self.termination_policy, TerminationPolicy):
            raise TypeError('termination_policy must be a TerminationPolicy')
        if self.grid_size < 1:
            raise ValueError('grid_size must be at least 1')
        if self.ant_count < 1:
            raise ValueError('ant_count must be at least 1')
        if self.max_steps < 1:
            raise ValueError('max_steps must be at least 1')
        if not self.feeders:
            raise ValueError('at least one feeder is required')
        feeder_ids = [feeder.feeder_id for feeder in self.feeders]
        if len(feeder_ids) != len(set(feeder_ids)):
            raise ValueError('feeder_id values must be unique')
        if 'uncommitted' in feeder_ids:
            raise ValueError("feeder_id 'uncommitted' is reserved for ant state")
        feeder_positions = [feeder.position for feeder in self.feeders]
        if len(feeder_positions) != len(set(feeder_positions)):
            raise ValueError('feeder positions must be unique')
        for label, position in [('nest', self.nest), *[
            (f'feeder {feeder.feeder_id}', feeder.position)
            for feeder in self.feeders
        ]]:
            if not (0 <= position.x < self.grid_size and 0 <= position.y < self.grid_size):
                raise ValueError(f'{label} position must be inside the grid')


@dataclass
class Ant:
    ant_id: int
    position: Position
    commitment: str | None = None
    holding_food: bool = False


@dataclass(frozen=True)
class RunResult:
    seed: int
    steps: int
    reason: TerminationReason
    nest_food: int
    carried_food: int
    feeder_food: dict[str, int]
    commitment_counts: dict[str | None, int]


class Simulation:
    def __init__(
        self,
        config: SimulationConfig,
        *,
        ants: Sequence[Ant] | None = None,
        rng: RandomSource | None = None,
        rng_seed: int | None = None,
    ) -> None:
        self.config = config
        self.feeders = {feeder.feeder_id: feeder for feeder in config.feeders}
        self.feeder_food = {
            feeder.feeder_id: feeder.food
            for feeder in config.feeders
        }
        self.initial_food = sum(self.feeder_food.values())
        self.nest_food = 0
        self.steps = 0
        if rng is None:
            if rng_seed is not None:
                raise ValueError('rng_seed is only valid with a custom random source')
            self.rng = random.Random(config.seed)
            self.result_seed: int | None = config.seed
        else:
            self.rng = rng
            self.result_seed = rng_seed
        self.ants = list(ants) if ants is not None else [
            Ant(ant_id, config.nest)
            for ant_id in range(1, config.ant_count + 1)
        ]
        self.last_discoveries: tuple[tuple[int, str], ...] = ()
        self.last_recruitments: tuple[tuple[int, str], ...] = ()
        self._step_discoveries: list[tuple[int, str]] = []
        self._step_recruitments: list[tuple[int, str]] = []
        if ants is not None and any(ant.holding_food for ant in self.ants):
            raise ValueError('supplied ants must start with holding_food=False')
        self._validate_ants()

    def _validate_ants(self) -> None:
        if len(self.ants) != self.config.ant_count:
            raise ValueError('ant_count must match the supplied ants')
        ant_ids = [ant.ant_id for ant in self.ants]
        if len(ant_ids) != len(set(ant_ids)):
            raise ValueError('ant_id values must be unique')
        for ant in self.ants:
            if not (
                0 <= ant.position.x < self.config.grid_size
                and 0 <= ant.position.y < self.config.grid_size
            ):
                raise ValueError('ant position must be inside the grid')
            if ant.commitment is not None and ant.commitment not in self.feeders:
                raise ValueError('ant commitment must reference a feeder')

    def update_social_state(self, *, committed_at_start: frozenset[int]) -> None:
        """Apply one synchronous recruitment/attrition phase.

        Each eligible recruiter at the nest selects at most one uncommitted ant
        at the nest and performs one Bernoulli recruitment attempt. State changes
        are queued and applied after all decisions, preventing same-step
        recruitment chains. Attrition applies only to ants that were committed
        at phase start.
        """
        ants_by_id = {ant.ant_id: ant for ant in self.ants}
        commitments_at_phase_start = {
            ant.ant_id: ant.commitment
            for ant in self.ants
        }
        uncommitted_at_phase_start = {
            ant_id
            for ant_id, commitment in commitments_at_phase_start.items()
            if commitment is None
        }
        proposals: dict[int, list[str]] = defaultdict(list)

        for recruiter_id in sorted(committed_at_start):
            recruiter = ants_by_id.get(recruiter_id)
            if (
                recruiter is None
                or recruiter.commitment is None
                or recruiter.position != self.config.nest
                or recruiter.holding_food
            ):
                continue
            feeder = self.feeders[recruiter.commitment]
            candidates = sorted(
                (
                    ants_by_id[ant_id]
                    for ant_id in uncommitted_at_phase_start
                    if ants_by_id[ant_id].position == self.config.nest
                ),
                key=lambda ant: ant.ant_id,
            )
            if not candidates:
                continue
            target = self.rng.choice(candidates)
            if self._event_occurs(feeder.recruitment_rate):
                proposals[target.ant_id].append(recruiter.commitment)

        attrited = set()
        for ant_id in sorted(committed_at_start):
            ant = ants_by_id.get(ant_id)
            if ant is None or ant.commitment is None:
                continue
            if self._event_occurs(self.feeders[ant.commitment].attrition_rate):
                attrited.add(ant_id)

        for ant_id in attrited:
            ants_by_id[ant_id].commitment = None
        for target_id, feeder_ids in sorted(proposals.items()):
            choices = sorted(feeder_ids)
            commitment = (
                choices[0] if len(choices) == 1 else self.rng.choice(choices)
            )
            ants_by_id[target_id].commitment = commitment
            self._step_recruitments.append((target_id, commitment))

    def step(self) -> TerminationReason | None:
        if self.steps >= self.config.max_steps:
            raise RuntimeError('simulation has reached max_steps')
        if self._termination_reason() is not None:
            raise RuntimeError('simulation has already reached its termination condition')
        self._step_discoveries = []
        self._step_recruitments = []
        committed_at_start = frozenset(
            ant.ant_id
            for ant in self.ants
            if ant.commitment is not None
        )
        for ant in sorted(self.ants, key=lambda item: item.ant_id):
            self._move_ant(ant)
        self.update_social_state(committed_at_start=committed_at_start)
        self.last_discoveries = tuple(self._step_discoveries)
        self.last_recruitments = tuple(self._step_recruitments)
        self.steps += 1
        self.assert_invariants()
        return self.termination_reason()

    def run(self) -> RunResult:
        if self.result_seed is None:
            raise ValueError('a custom random source requires rng_seed for a recorded run')
        existing_reason = self.termination_reason()
        if existing_reason is not None:
            return self._result(existing_reason)
        remaining_steps = max(0, self.config.max_steps - self.steps)
        for _ in range(remaining_steps):
            reason = self.step()
            if reason is not None:
                return self._result(reason)
        return self._result(self._step_bound_reason())

    def termination_reason(self) -> TerminationReason | None:
        depletion_reason = self._termination_reason()
        if depletion_reason is not None:
            return depletion_reason
        if self.steps >= self.config.max_steps:
            return self._step_bound_reason()
        return None

    def _step_bound_reason(self) -> TerminationReason:
        if self.config.termination_policy is TerminationPolicy.FIXED_STEPS:
            return TerminationReason.FIXED_HORIZON_COMPLETE
        return TerminationReason.MAX_STEPS_CENSORED

    def _move_ant(self, ant: Ant) -> None:
        if ant.holding_food:
            if ant.position == self.config.nest:
                ant.holding_food = False
                self.nest_food += 1
            else:
                ant.position = self._step_towards(ant.position, self.config.nest)
            return

        if ant.commitment is not None:
            feeder = self.feeders[ant.commitment]
            if ant.position != feeder.position:
                ant.position = self._step_towards(ant.position, feeder.position)
            if ant.position == feeder.position:
                self._pick_up_food(ant, feeder.feeder_id)
            return

        neighbors = self._valid_neighbors(ant.position)
        if neighbors:
            ant.position = self.rng.choice(neighbors)
        self._discover_feeder(ant)

    def _valid_neighbors(self, position: Position) -> list[Position]:
        candidates = [
            Position(position.x, position.y + 1),
            Position(position.x, position.y - 1),
            Position(position.x + 1, position.y),
            Position(position.x - 1, position.y),
        ]
        return [
            candidate
            for candidate in candidates
            if 0 <= candidate.x < self.config.grid_size
            and 0 <= candidate.y < self.config.grid_size
        ]

    @staticmethod
    def _step_towards(position: Position, goal: Position) -> Position:
        x_distance = abs(position.x - goal.x)
        y_distance = abs(position.y - goal.y)
        if x_distance > y_distance:
            return Position(position.x + (1 if position.x < goal.x else -1), position.y)
        if y_distance:
            return Position(position.x, position.y + (1 if position.y < goal.y else -1))
        return position

    def _discover_feeder(self, ant: Ant) -> None:
        for feeder_id in sorted(self.feeders):
            feeder = self.feeders[feeder_id]
            if ant.position != feeder.position:
                continue
            if self._event_occurs(feeder.quality):
                ant.commitment = feeder_id
                self._step_discoveries.append((ant.ant_id, feeder_id))
                self._pick_up_food(ant, feeder_id)
            return

    def _pick_up_food(self, ant: Ant, feeder_id: str) -> None:
        if self.feeder_food[feeder_id] <= 0:
            return
        self.feeder_food[feeder_id] -= 1
        ant.holding_food = True

    def _termination_reason(self) -> TerminationReason | None:
        remaining = tuple(self.feeder_food.values())
        if (
            self.config.termination_policy is TerminationPolicy.FIRST_FEEDER_DEPLETED
            and any(food == 0 for food in remaining)
        ):
            return TerminationReason.FIRST_FEEDER_DEPLETED
        if (
            self.config.termination_policy is TerminationPolicy.ALL_FEEDERS_DEPLETED
            and all(food == 0 for food in remaining)
        ):
            return TerminationReason.ALL_FEEDERS_DEPLETED
        return None

    def _result(self, reason: TerminationReason) -> RunResult:
        counts: dict[str | None, int] = {
            None: 0,
            **{feeder_id: 0 for feeder_id in self.feeders},
        }
        for ant in self.ants:
            counts[ant.commitment] += 1
        return RunResult(
            seed=self._recorded_seed,
            steps=self.steps,
            reason=reason,
            nest_food=self.nest_food,
            carried_food=sum(ant.holding_food for ant in self.ants),
            feeder_food=dict(self.feeder_food),
            commitment_counts=dict(counts),
        )

    @property
    def _recorded_seed(self) -> int:
        if self.result_seed is None:
            raise RuntimeError('run seed provenance is unavailable')
        return self.result_seed

    def assert_invariants(self) -> None:
        self._validate_ants()
        if any(food < 0 for food in self.feeder_food.values()):
            raise AssertionError('feeder food must not be negative')
        accounted_food = (
            self.nest_food
            + sum(ant.holding_food for ant in self.ants)
            + sum(self.feeder_food.values())
        )
        if accounted_food != self.initial_food:
            raise AssertionError('food must be conserved')

    def _event_occurs(self, probability: float) -> bool:
        if probability <= 0:
            return False
        if probability >= 1:
            return True
        return self.rng.random() < probability
