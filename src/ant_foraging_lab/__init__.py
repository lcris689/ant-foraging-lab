"""Reproducible ant-foraging simulation package."""

from .model import (
    Ant,
    FeederConfig,
    Position,
    RunResult,
    Simulation,
    SimulationConfig,
    TerminationPolicy,
    TerminationReason,
)

__all__ = [
    'Ant',
    'FeederConfig',
    'Position',
    'RunResult',
    'Simulation',
    'SimulationConfig',
    'TerminationPolicy',
    'TerminationReason',
]
