from dataclasses import replace

from .model import FeederConfig, Position, SimulationConfig


def three_feeder_scenario(*, seed: int, max_steps: int) -> SimulationConfig:
    """Return the reference three-feeder scenario as explicit data."""
    return SimulationConfig(
        grid_size=100,
        nest=Position(50, 50),
        feeders=(
            FeederConfig('A', Position(25, 75), 0.75, 0.75, 0.009, 1000),
            FeederConfig('B', Position(75, 25), 0.75, 0.75, 0.009, 1000),
            FeederConfig('C', Position(75, 75), 0.75, 0.75, 0.009, 1000),
        ),
        ant_count=200,
        max_steps=max_steps,
        seed=seed,
    )


def no_recruitment_three_feeder(*, seed: int, max_steps: int) -> SimulationConfig:
    """Return a matched baseline with feeder recruitment disabled."""
    treatment = three_feeder_scenario(seed=seed, max_steps=max_steps)
    return replace(
        treatment,
        feeders=tuple(
            replace(feeder, recruitment_rate=0.0)
            for feeder in treatment.feeders
        ),
    )


def guided_demo_scenario(*, seed: int, max_steps: int = 400) -> SimulationConfig:
    """Return a compact scenario that makes the model's mechanisms observable."""
    return SimulationConfig(
        grid_size=40,
        nest=Position(20, 20),
        feeders=(
            FeederConfig('A', Position(10, 20), 1.0, 0.75, 0.003, 1000),
            FeederConfig('B', Position(30, 20), 1.0, 0.75, 0.003, 1000),
            FeederConfig('C', Position(20, 30), 1.0, 0.75, 0.003, 1000),
        ),
        ant_count=120,
        max_steps=max_steps,
        seed=seed,
    )


def no_recruitment_guided_demo(*, seed: int, max_steps: int = 400) -> SimulationConfig:
    """Return the guided demo with recruitment disabled for comparison."""
    treatment = guided_demo_scenario(seed=seed, max_steps=max_steps)
    return replace(
        treatment,
        feeders=tuple(
            replace(feeder, recruitment_rate=0.0)
            for feeder in treatment.feeders
        ),
    )
