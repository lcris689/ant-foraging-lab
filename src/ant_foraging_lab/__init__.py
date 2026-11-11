"""Reproducible ant-foraging simulation package."""

from ._version import MODEL_VERSION, TRACE_SCHEMA_VERSION, __version__
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
    'MODEL_VERSION',
    'TRACE_SCHEMA_VERSION',
    'Ant',
    'FeederConfig',
    'Position',
    'RunResult',
    'Simulation',
    'SimulationConfig',
    'TerminationPolicy',
    'TerminationReason',
    '__version__',
]
