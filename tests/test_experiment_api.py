from fastapi.testclient import TestClient

from ant_foraging_lab.experiment import run_experiment
from ant_foraging_lab.model import (
    FeederConfig,
    Position,
    SimulationConfig,
)
from ant_foraging_lab.web import app

client = TestClient(app)


def small_config() -> SimulationConfig:
    return SimulationConfig(
        grid_size=8,
        nest=Position(4, 4),
        feeders=(
            FeederConfig('A', Position(1, 1), 1.0, 0.4, 0.05, 12),
            FeederConfig('B', Position(6, 6), 0.8, 0.3, 0.04, 12),
        ),
        ant_count=8,
        max_steps=6,
        seed=7,
    )


def api_payload() -> dict:
    return {
        'seed': 7,
        'grid_size': 8,
        'nest': {'x': 4, 'y': 4},
        'ant_count': 8,
        'max_steps': 6,
        'frame_stride': 2,
        'termination_policy': 'fixed_steps',
        'feeders': [
            {
                'feeder_id': 'A',
                'position': {'x': 1, 'y': 1},
                'quality': 1.0,
                'recruitment_rate': 0.4,
                'attrition_rate': 0.05,
                'food': 12,
            },
            {
                'feeder_id': 'B',
                'position': {'x': 6, 'y': 6},
                'quality': 0.8,
                'recruitment_rate': 0.3,
                'attrition_rate': 0.04,
                'food': 12,
            },
        ],
    }


def test_experiment_trace_includes_initial_sampled_and_final_frames():
    trace = run_experiment(small_config(), frame_stride=2)

    assert [frame.step for frame in trace.frames] == [0, 2, 4, 6]
    assert trace.result.steps == 6
    assert trace.result.seed == 7
    assert trace.frames[-1].nest_food == trace.result.nest_food
    assert (
        trace.result.nest_food
        + trace.result.carried_food
        + sum(trace.result.feeder_food.values())
        == 24
    )
    assert len(trace.frames[0].ants) == 8


def test_experiment_trace_is_reproducible_for_the_same_seed():
    first = run_experiment(small_config(), frame_stride=2)
    second = run_experiment(small_config(), frame_stride=2)

    assert first == second


def test_run_api_returns_browser_ready_trace():
    response = client.post('/api/runs', json=api_payload())

    assert response.status_code == 200
    body = response.json()
    assert body['result']['steps'] == 6
    assert body['result']['reason'] == 'max_steps'
    assert [frame['step'] for frame in body['frames']] == [0, 2, 4, 6]
    assert body['config']['seed'] == 7
    assert body['config']['feeders'][0]['feeder_id'] == 'A'


def test_run_api_rejects_a_feeder_outside_the_grid():
    payload = api_payload()
    payload['feeders'][0]['position'] = {'x': 8, 'y': 1}

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'inside the grid' in response.text


def test_run_api_rejects_duplicate_feeder_identifiers():
    payload = api_payload()
    payload['feeders'][1]['feeder_id'] = 'A'

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'feeder_id values must be unique' in response.text


def test_run_api_bounds_the_number_of_sampled_frames():
    payload = api_payload()
    payload['max_steps'] = 501
    payload['frame_stride'] = 1

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'at most 500 sampled frames' in response.text


def test_home_page_serves_the_interactive_lab():
    response = client.get('/')

    assert response.status_code == 200
    assert 'Ant Foraging Lab' in response.text
    assert 'experiment-form' in response.text
