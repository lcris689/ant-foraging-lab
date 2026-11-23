from fastapi.testclient import TestClient

from ant_foraging_lab.experiment import run_experiment, trace_to_dict
from ant_foraging_lab.model import (
    FeederConfig,
    Position,
    Simulation,
    SimulationConfig,
)
from ant_foraging_lab.scenarios import guided_demo_scenario
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


def test_experiment_trace_records_significant_events_between_sampled_frames():
    config = SimulationConfig(
        grid_size=3,
        nest=Position(1, 1),
        feeders=(
            FeederConfig('A', Position(1, 0), 1.0, 1.0, 0.0, 20),
        ),
        ant_count=8,
        max_steps=12,
        seed=0,
    )

    trace = run_experiment(config, frame_stride=4)

    assert [(event.kind, event.step, event.feeder_id) for event in trace.events] == [
        ('feeder_discovered', 3, 'A'),
        ('first_delivery', 5, None),
        ('first_recruitment', 10, 'A'),
        ('delivery_milestone', 11, None),
        ('run_complete', 12, None),
    ]
    assert trace.events[3].value == 10
    assert trace.frames[-1].step == trace.result.steps
    assert trace.result.nest_food == 11
    assert trace.result == Simulation(config).run()


def test_feeder_at_nest_is_not_misreported_as_recruitment():
    config = SimulationConfig(
        grid_size=3,
        nest=Position(1, 1),
        feeders=(FeederConfig('A', Position(1, 1), 1.0, 0.0, 0.0, 100),),
        ant_count=1,
        max_steps=20,
        seed=0,
    )

    trace = run_experiment(config, frame_stride=2)

    assert any(event.kind == 'feeder_discovered' for event in trace.events)
    assert all(event.kind != 'first_recruitment' for event in trace.events)


def test_delivery_is_logged_before_recruitment_when_both_share_a_step():
    trace = run_experiment(
        guided_demo_scenario(seed=145, max_steps=50),
        frame_stride=10,
    )

    shared_step_events = [event.kind for event in trace.events if event.step == 41]
    assert shared_step_events.index('first_delivery') < shared_step_events.index(
        'first_recruitment'
    )


def test_feeder_depletion_is_logged_before_same_step_recruitment():
    config = SimulationConfig(
        grid_size=3,
        nest=Position(1, 1),
        feeders=(FeederConfig('A', Position(1, 2), 1.0, 1.0, 0.0, 4),),
        ant_count=3,
        max_steps=30,
        seed=7,
    )

    trace = run_experiment(config, frame_stride=10)

    shared_step_events = [event.kind for event in trace.events if event.step == 8]
    assert shared_step_events.index('feeder_depleted') < shared_step_events.index(
        'first_recruitment'
    )


def test_export_records_versioned_model_and_rng_provenance():
    trace = run_experiment(
        small_config(),
        frame_stride=2,
        scenario_name='small_test',
    )

    data = trace_to_dict(trace)

    assert data['provenance']['schema_version'] == 2
    assert data['provenance']['package_version'] == '0.3.0'
    assert data['provenance']['model_version'] == '0.2.0'
    assert data['provenance']['scenario_name'] == 'small_test'
    assert data['provenance']['rng_family'] == 'python.random.Random'
    assert data['provenance']['python_version']


def test_run_api_returns_browser_ready_trace():
    response = client.post('/api/runs', json=api_payload())

    assert response.status_code == 200
    body = response.json()
    assert body['frames'][0]['step'] == 0
    assert body['frames'][-1]['step'] == body['result']['steps']
    assert [frame['step'] for frame in body['frames']] == [0, 2, 4, 6]
    assert body['config']['seed'] == 7
    assert body['config']['feeders'][0]['feeder_id'] == 'A'


def test_api_preserves_selected_preset_in_export_provenance():
    request = api_payload()
    request['scenario_name'] = 'guided_demo'

    response = client.post('/api/runs', json=request)

    assert response.status_code == 200
    assert response.json()['provenance']['scenario_name'] == 'guided_demo'


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


def test_run_api_rejects_the_reserved_uncommitted_feeder_identifier():
    payload = api_payload()
    payload['feeders'][0]['feeder_id'] = 'uncommitted'

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'reserved' in response.text


def test_run_api_bounds_the_number_of_sampled_frames():
    payload = api_payload()
    payload['max_steps'] = 501
    payload['frame_stride'] = 1

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'at most 500 sampled frames' in response.text


def test_run_api_rejects_requests_above_the_compute_budget():
    payload = api_payload()
    payload['ant_count'] = 500
    payload['max_steps'] = 1000
    payload['frame_stride'] = 2

    response = client.post('/api/runs', json=payload)

    assert response.status_code == 422
    assert 'compute budget' in response.text


def test_home_page_serves_the_interactive_lab():
    response = client.get('/')

    assert response.status_code == 200
    assert 'Ant Foraging Lab' in response.text
    assert 'experiment-form' in response.text
    assert 'role="tab"' in response.text
    assert 'aria-selected="true"' in response.text
    assert 'id="api-status"' in response.text
    assert 'role="status"' in response.text
    assert 'id="preset"' in response.text
    assert 'Guided mechanism demo' in response.text
    assert 'Variable guide' in response.text
    for variable in (
        'Seed',
        'Ants',
        'Grid size',
        'Max steps',
        'Sample every',
        'Stop rule',
        'Nest X / Y',
        'Feeder X / Y',
        'Quality',
        'Food',
        'Recruitment',
        'Attrition',
    ):
        assert f'<dt>{variable}</dt>' in response.text
    assert 'id="event-log"' in response.text
    assert 'role="log"' in response.text
    assert 'Your browser does not support the simulation canvas.' in response.text


def test_browser_lab_does_not_start_compute_on_page_load():
    response = client.get('/app.js')

    assert response.status_code == 200
    assert response.text.rstrip().endswith('checkHealth();')


def test_browser_lab_defines_presets_and_replays_events_from_the_start():
    response = client.get('/app.js')

    assert response.status_code == 200
    assert 'const PRESETS = {' in response.text
    assert 'guided:' in response.text
    assert 'reference:' in response.text
    assert 'noRecruitment:' in response.text
    assert 'currentFrameIndex = 0;' in response.text
    assert 'function renderEventLog' in response.text
    assert "scenarioName: 'guided_demo'" in response.text
    assert "scenarioName: 'reference_experiment'" in response.text
    assert "scenarioName: 'guided_no_recruitment'" in response.text
    assert "scenario_name: PRESETS[presetSelect.value]?.scenarioName || 'custom'" in response.text


def test_mobile_layout_places_configuration_before_the_empty_simulation():
    response = client.get('/styles.css')

    assert response.status_code == 200
    mobile_rules = response.text.split('@media (max-width: 760px)', maxsplit=1)[1]
    assert '.controls-panel { order: 1; }' in mobile_rules
    assert '.simulation-panel { order: 2;' in mobile_rules
