from collections import deque

import pytest

from ant_foraging_lab.model import (
    Ant,
    FeederConfig,
    Position,
    Simulation,
    SimulationConfig,
    TerminationPolicy,
    TerminationReason,
)
from ant_foraging_lab.scenarios import three_feeder_scenario


class ScriptedRandom:
    def __init__(self, values):
        self.values = deque(values)
        self.random_calls = 0
        self.choice_calls = 0

    def random(self):
        self.random_calls += 1
        return self.values.popleft()

    def choice(self, values):
        self.choice_calls += 1
        return min(values, key=lambda value: getattr(value, 'ant_id', value))


def make_simulation(ants, *, recruitment_rate=0.5, attrition_rate=0.0, random_values=(0.0,)):
    config = SimulationConfig(
        grid_size=5,
        nest=Position(0, 0),
        feeders=(
            FeederConfig(
                feeder_id='A',
                position=Position(4, 4),
                quality=1.0,
                recruitment_rate=recruitment_rate,
                attrition_rate=attrition_rate,
                food=100,
            ),
        ),
        ant_count=len(ants),
        max_steps=100,
        seed=689,
    )
    rng = ScriptedRandom(random_values)
    return Simulation(config, ants=ants, rng=rng), rng


def commitments(simulation):
    return {ant.ant_id: ant.commitment for ant in simulation.ants}


def test_each_recruiter_makes_one_probability_attempt():
    simulation, rng = make_simulation(
        [
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0)),
            Ant(3, Position(0, 0)),
        ],
        recruitment_rate=0.5,
        random_values=(0.9,),
    )

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: 'A', 2: None, 3: None}
    assert rng.random_calls == 1
    assert rng.choice_calls == 1


def test_recruitment_occurs_between_ants_co_located_at_the_nest():
    simulation, _ = make_simulation(
        [
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0)),
        ],
        recruitment_rate=1.0,
    )

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: 'A', 2: 'A'}


def test_recruitment_does_not_occur_when_ants_meet_away_from_the_nest():
    simulation, rng = make_simulation(
        [
            Ant(1, Position(2, 2), commitment='A'),
            Ant(2, Position(2, 3)),
        ],
        recruitment_rate=1.0,
    )

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: 'A', 2: None}
    assert rng.choice_calls == 0


def test_carrying_ant_cannot_recruit_until_food_is_deposited():
    simulation, rng = make_simulation(
        [
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0)),
        ],
        recruitment_rate=1.0,
    )
    simulation.ants[0].holding_food = True

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: 'A', 2: None}
    assert rng.choice_calls == 0


def test_recruited_ant_cannot_recruit_in_the_same_timestep():
    simulation, _ = make_simulation(
        [
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0)),
            Ant(3, Position(0, 0)),
        ],
        recruitment_rate=1.0,
        random_values=(0.0,),
    )

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: 'A', 2: 'A', 3: None}


def test_newly_recruited_ant_does_not_suffer_same_step_attrition():
    simulation, _ = make_simulation(
        [
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0)),
        ],
        recruitment_rate=1.0,
        attrition_rate=1.0,
        random_values=(0.0, 0.0),
    )

    simulation.update_social_state(committed_at_start=frozenset({1}))

    assert commitments(simulation) == {1: None, 2: 'A'}


def test_social_updates_do_not_depend_on_ant_list_order():
    ants = [
        Ant(1, Position(0, 0), commitment='A'),
        Ant(2, Position(0, 0)),
        Ant(3, Position(0, 0), commitment='A'),
        Ant(4, Position(0, 0)),
    ]
    reversed_ants = list(reversed([
        Ant(1, Position(0, 0), commitment='A'),
        Ant(2, Position(0, 0)),
        Ant(3, Position(0, 0), commitment='A'),
        Ant(4, Position(0, 0)),
    ]))
    first, _ = make_simulation(ants, recruitment_rate=1.0, random_values=(0.0, 0.0))
    second, _ = make_simulation(reversed_ants, recruitment_rate=1.0, random_values=(0.0, 0.0))

    first.update_social_state(committed_at_start=frozenset({1, 3}))
    second.update_social_state(committed_at_start=frozenset({1, 3}))

    assert commitments(first) == commitments(second) == {
        1: 'A',
        2: 'A',
        3: 'A',
        4: None,
    }


def test_competing_successful_recruiters_resolve_one_seeded_feeder_claim():
    config = SimulationConfig(
        grid_size=5,
        nest=Position(0, 0),
        feeders=(
            FeederConfig('A', Position(0, 0), 1.0, 1.0, 0.0, 10),
            FeederConfig('B', Position(4, 4), 1.0, 1.0, 0.0, 10),
        ),
        ant_count=3,
        max_steps=10,
        seed=1,
    )
    rng = ScriptedRandom(())
    simulation = Simulation(
        config,
        ants=[
            Ant(1, Position(0, 0), commitment='A'),
            Ant(2, Position(0, 0), commitment='B'),
            Ant(3, Position(0, 0)),
        ],
        rng=rng,
    )

    simulation.update_social_state(committed_at_start=frozenset({1, 2}))

    assert simulation.ants[2].commitment == 'A'
    assert rng.choice_calls == 3


def test_one_cell_grid_reaches_its_step_bound_without_hanging():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 10),),
        ant_count=1,
        max_steps=3,
        seed=1,
    )

    result = Simulation(config).run()

    assert result.steps == 3
    assert result.reason.value == 'fixed_horizon_complete'


def test_depletion_run_reports_censoring_when_the_safety_bound_is_reached():
    config = SimulationConfig(
        grid_size=2,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(1, 1), 0.0, 0.0, 0.0, 10),),
        ant_count=1,
        max_steps=2,
        seed=1,
        termination_policy=TerminationPolicy.ALL_FEEDERS_DEPLETED,
    )

    result = Simulation(config).run()

    assert result.steps == 2
    assert result.reason.value == 'max_steps_censored'


def test_first_depletion_policy_returns_a_structured_reason():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 1.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=10,
        seed=1,
        termination_policy=TerminationPolicy.FIRST_FEEDER_DEPLETED,
    )

    result = Simulation(config).run()

    assert result.steps == 1
    assert result.reason is TerminationReason.FIRST_FEEDER_DEPLETED
    assert result.feeder_food == {'A': 0}
    assert result.carried_food == 1


def test_all_depleted_policy_returns_a_structured_reason():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 1.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=10,
        seed=1,
        termination_policy=TerminationPolicy.ALL_FEEDERS_DEPLETED,
    )

    result = Simulation(config).run()

    assert result.steps == 1
    assert result.reason is TerminationReason.ALL_FEEDERS_DEPLETED


def test_depletion_policy_stops_at_step_zero_when_feeder_starts_empty():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 0),),
        ant_count=1,
        max_steps=10,
        seed=1,
        termination_policy=TerminationPolicy.FIRST_FEEDER_DEPLETED,
    )

    result = Simulation(config).run()

    assert result.steps == 0
    assert result.reason is TerminationReason.FIRST_FEEDER_DEPLETED


def test_step_cannot_mutate_a_simulation_after_depletion_termination():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 1.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=10,
        seed=1,
        termination_policy=TerminationPolicy.FIRST_FEEDER_DEPLETED,
    )
    simulation = Simulation(config)
    completed = simulation.run()

    with pytest.raises(RuntimeError, match='termination condition'):
        simulation.step()

    assert simulation.run() == completed
    assert simulation.steps == 1


def test_newly_discovered_ant_does_not_suffer_same_step_attrition():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 1.0, 0.0, 1.0, 2),),
        ant_count=1,
        max_steps=1,
        seed=1,
    )
    simulation = Simulation(config)

    simulation.step()

    assert simulation.ants[0].commitment == 'A'


def test_seeded_runs_are_repeatable():
    config = SimulationConfig(
        grid_size=5,
        nest=Position(2, 2),
        feeders=(
            FeederConfig('A', Position(0, 0), 1.0, 0.4, 0.1, 20),
            FeederConfig('B', Position(4, 4), 1.0, 0.4, 0.1, 20),
        ),
        ant_count=12,
        max_steps=30,
        seed=689,
    )

    first = Simulation(config)
    second = Simulation(config)

    assert first.run() == second.run()
    assert [
        (ant.ant_id, ant.position, ant.commitment, ant.holding_food)
        for ant in first.ants
    ] == [
        (ant.ant_id, ant.position, ant.commitment, ant.holding_food)
        for ant in second.ants
    ]


def test_full_steps_are_independent_of_internal_ant_list_order():
    config = SimulationConfig(
        grid_size=5,
        nest=Position(2, 2),
        feeders=(
            FeederConfig('A', Position(0, 0), 0.7, 0.6, 0.4, 10),
            FeederConfig('B', Position(4, 4), 0.8, 0.5, 0.3, 10),
        ),
        ant_count=5,
        max_steps=10,
        seed=42,
    )
    ants = [
        Ant(1, Position(1, 1), commitment='A'),
        Ant(2, Position(3, 3), commitment='B'),
        Ant(3, Position(2, 1)),
        Ant(4, Position(2, 3)),
        Ant(5, Position(2, 2)),
    ]
    forward = Simulation(config, ants=[Ant(**vars(ant)) for ant in ants])
    reverse = Simulation(config, ants=[Ant(**vars(ant)) for ant in reversed(ants)])

    assert forward.run() == reverse.run()
    assert sorted(forward.ants, key=lambda ant: ant.ant_id) == sorted(
        reverse.ants,
        key=lambda ant: ant.ant_id,
    )


def test_run_preserves_ant_and_food_invariants():
    config = SimulationConfig(
        grid_size=5,
        nest=Position(2, 2),
        feeders=(FeederConfig('A', Position(0, 0), 1.0, 0.5, 0.05, 20),),
        ant_count=10,
        max_steps=40,
        seed=568,
    )
    simulation = Simulation(config)

    result = simulation.run()

    assert result.nest_food + result.carried_food + sum(result.feeder_food.values()) == 20
    assert len(simulation.ants) == 10
    assert all(0 <= ant.position.x < 5 and 0 <= ant.position.y < 5 for ant in simulation.ants)


def test_run_result_includes_zero_counts_for_every_feeder():
    config = SimulationConfig(
        grid_size=2,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(1, 1), 0.0, 0.0, 0.0, 20),),
        ant_count=2,
        max_steps=1,
        seed=1,
    )

    result = Simulation(config).run()

    assert result.commitment_counts == {None: 2, 'A': 0}


def test_feeders_cannot_share_a_position():
    with pytest.raises(ValueError, match='feeder positions must be unique'):
        SimulationConfig(
            grid_size=5,
            nest=Position(2, 2),
            feeders=(
                FeederConfig('A', Position(0, 0), 1.0, 0.5, 0.1, 20),
                FeederConfig('B', Position(0, 0), 1.0, 0.5, 0.1, 20),
            ),
            ant_count=10,
            max_steps=40,
            seed=1,
        )


def test_feeder_id_cannot_use_the_uncommitted_state_label():
    with pytest.raises(ValueError, match='reserved'):
        SimulationConfig(
            grid_size=5,
            nest=Position(2, 2),
            feeders=(
                FeederConfig('uncommitted', Position(0, 0), 1.0, 0.5, 0.1, 20),
            ),
            ant_count=10,
            max_steps=40,
            seed=1,
        )


@pytest.mark.parametrize(
    ('field_name', 'invalid_value'),
    [
        ('grid_size', 5.5),
        ('ant_count', True),
        ('max_steps', 40.0),
        ('seed', '1'),
    ],
)
def test_simulation_config_rejects_non_integer_core_values(field_name, invalid_value):
    values = {
        'grid_size': 5,
        'nest': Position(2, 2),
        'feeders': (
            FeederConfig('A', Position(0, 0), 1.0, 0.5, 0.1, 20),
        ),
        'ant_count': 10,
        'max_steps': 40,
        'seed': 1,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError, match=field_name):
        SimulationConfig(**values)


def test_position_coordinates_and_feeder_food_must_be_integers():
    with pytest.raises(TypeError, match='position coordinates'):
        Position(1.5, 2)

    with pytest.raises(TypeError, match='food'):
        FeederConfig('A', Position(0, 0), 1.0, 0.5, 0.1, 20.5)


def test_feeder_identifier_must_be_a_non_whitespace_string():
    with pytest.raises(TypeError, match='feeder_id'):
        FeederConfig(1, Position(0, 0), 1.0, 0.5, 0.1, 20)

    with pytest.raises(ValueError, match='feeder_id'):
        FeederConfig('   ', Position(0, 0), 1.0, 0.5, 0.1, 20)


def test_three_feeder_scenario_is_machine_readable():
    config = three_feeder_scenario(seed=689, max_steps=2000)

    assert config.grid_size == 100
    assert config.nest == Position(50, 50)
    assert config.ant_count == 200
    assert config.seed == 689
    assert config.max_steps == 2000
    assert [feeder.feeder_id for feeder in config.feeders] == ['A', 'B', 'C']
    assert [feeder.position for feeder in config.feeders] == [
        Position(25, 75),
        Position(75, 25),
        Position(75, 75),
    ]


def test_run_cannot_advance_past_the_absolute_step_bound():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=2,
        seed=1,
    )
    simulation = Simulation(config)

    first = simulation.run()
    second = simulation.run()

    assert first == second
    assert simulation.steps == 2


def test_step_cannot_advance_past_the_absolute_step_bound():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=1,
        seed=1,
    )
    simulation = Simulation(config)
    simulation.run()

    with pytest.raises(RuntimeError, match='max_steps'):
        simulation.step()

    assert simulation.steps == 1


def test_committed_ant_cannot_collect_food_away_from_its_feeder():
    config = SimulationConfig(
        grid_size=5,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(4, 4), 1.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=1,
        seed=1,
    )
    simulation = Simulation(
        config,
        ants=[Ant(1, Position(0, 0), commitment='A')],
    )

    simulation.step()

    assert simulation.ants[0].position == Position(0, 1)
    assert simulation.ants[0].holding_food is False
    assert simulation.feeder_food == {'A': 1}


def test_termination_policy_must_be_an_enum_member():
    with pytest.raises(TypeError, match='termination_policy'):
        SimulationConfig(
            grid_size=1,
            nest=Position(0, 0),
            feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
            ant_count=1,
            max_steps=2,
            seed=1,
            termination_policy='fixed_steps',
        )


def test_supplied_ants_cannot_start_with_unaccounted_carried_food():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=1,
        seed=1,
    )

    with pytest.raises(ValueError, match='holding_food'):
        Simulation(config, ants=[Ant(1, Position(0, 0), holding_food=True)])


def test_custom_random_source_requires_explicit_seed_provenance_for_a_run():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=1,
        seed=689,
    )

    simulation = Simulation(config, rng=ScriptedRandom(()))

    with pytest.raises(ValueError, match='rng_seed'):
        simulation.run()


def test_custom_random_source_records_its_explicit_seed_provenance():
    config = SimulationConfig(
        grid_size=1,
        nest=Position(0, 0),
        feeders=(FeederConfig('A', Position(0, 0), 0.0, 0.0, 0.0, 1),),
        ant_count=1,
        max_steps=1,
        seed=689,
    )

    result = Simulation(config, rng=ScriptedRandom(()), rng_seed=123).run()

    assert result.seed == 123
