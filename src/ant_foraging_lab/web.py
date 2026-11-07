from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .experiment import run_experiment, trace_to_dict
from .model import FeederConfig, Position, SimulationConfig, TerminationPolicy


class PositionInput(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class FeederInput(BaseModel):
    feeder_id: str = Field(min_length=1, max_length=16)
    position: PositionInput
    quality: float = Field(ge=0, le=1)
    recruitment_rate: float = Field(ge=0, le=1)
    attrition_rate: float = Field(ge=0, le=1)
    food: int = Field(ge=1, le=100_000)


class RunRequest(BaseModel):
    seed: int = Field(ge=0, le=2**32 - 1)
    grid_size: int = Field(ge=2, le=150)
    nest: PositionInput
    ant_count: int = Field(ge=1, le=500)
    max_steps: int = Field(ge=1, le=5_000)
    frame_stride: int = Field(ge=1, le=250)
    termination_policy: TerminationPolicy
    feeders: list[FeederInput] = Field(min_length=1, max_length=5)

    @model_validator(mode='after')
    def validate_spatial_configuration(self) -> 'RunRequest':
        feeder_ids = [feeder.feeder_id for feeder in self.feeders]
        if len(feeder_ids) != len(set(feeder_ids)):
            raise ValueError('feeder_id values must be unique')
        feeder_positions = [
            (feeder.position.x, feeder.position.y)
            for feeder in self.feeders
        ]
        if len(feeder_positions) != len(set(feeder_positions)):
            raise ValueError('feeder positions must be unique')
        if self.max_steps > self.frame_stride * 500:
            raise ValueError('a run may contain at most 500 sampled frames')
        points = [('nest', self.nest), *[
            (f'feeder {feeder.feeder_id}', feeder.position)
            for feeder in self.feeders
        ]]
        for label, point in points:
            if point.x >= self.grid_size or point.y >= self.grid_size:
                raise ValueError(f'{label} position must be inside the grid')
        return self

    def to_config(self) -> SimulationConfig:
        return SimulationConfig(
            grid_size=self.grid_size,
            nest=Position(self.nest.x, self.nest.y),
            feeders=tuple(
                FeederConfig(
                    feeder_id=feeder.feeder_id,
                    position=Position(feeder.position.x, feeder.position.y),
                    quality=feeder.quality,
                    recruitment_rate=feeder.recruitment_rate,
                    attrition_rate=feeder.attrition_rate,
                    food=feeder.food,
                )
                for feeder in self.feeders
            ),
            ant_count=self.ant_count,
            max_steps=self.max_steps,
            seed=self.seed,
            termination_policy=self.termination_policy,
        )


app = FastAPI(
    title='Ant Foraging Lab',
    description='Run reproducible spatial ant-foraging experiments.',
    version='0.1.0',
)


@app.get('/api/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/api/runs')
def create_run(request: RunRequest) -> dict:
    trace = run_experiment(request.to_config(), frame_stride=request.frame_stride)
    return trace_to_dict(trace)


STATIC_DIRECTORY = Path(__file__).with_name('static')
app.mount('/', StaticFiles(directory=STATIC_DIRECTORY, html=True), name='static')


def main() -> None:
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000)