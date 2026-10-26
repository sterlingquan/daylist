"""Use an isolated SQLite file by default, or TEST_DATABASE_URL for PostgreSQL."""
import os
import tempfile
from pathlib import Path

_test_dir = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = os.getenv('TEST_DATABASE_URL', f'sqlite:///{Path(_test_dir.name) / "test.db"}')

import pytest
from fastapi.testclient import TestClient
from app.main import Base, app, engine


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)


def test_task_lifecycle_persistence_and_filters(client):
    assert client.get('/health').json() == {'status': 'ok'}
    payload = {'title': '  Ship the app  ', 'description': 'First release', 'priority': 'high', 'due_date': '2026-11-01'}
    result = client.post('/api/tasks', json=payload)
    assert result.status_code == 201
    task = result.json()
    assert task['title'] == 'Ship the app'
    assert task['due_date'] == '2026-11-01'
    task_id = task['id']
    # Independent request/session sees the committed record.
    assert client.get('/api/tasks').json() == [task]
    second = client.post('/api/tasks', json={'title': 'Buy groceries'}).json()
    assert client.get('/api/tasks?sort=newest').json()[0]['id'] == second['id']
    assert client.get('/api/tasks?sort=oldest').json()[0]['id'] == task_id
    assert len(client.get('/api/tasks?q=SHIP').json()) == 1
    assert client.get('/api/tasks?q=%25').json() == []
    updated = client.patch(f'/api/tasks/{task_id}', json={'completed': True, 'title': 'Published', 'due_date': None}).json()
    assert updated['completed'] is True
    assert updated['description'] == 'First release'
    assert updated['priority'] == 'high'
    assert updated['due_date'] is None
    assert len(client.get('/api/tasks?status=completed').json()) == 1
    assert len(client.get('/api/tasks?status=pending').json()) == 1
    assert client.patch(f'/api/tasks/{task_id}', json={'completed': False}).json()['completed'] is False
    # Recreate the application lifespan to verify the database outlives requests/startup.
    with TestClient(app) as reconnected:
        assert len(reconnected.get('/api/tasks').json()) == 2
    assert client.delete(f'/api/tasks/{task_id}').status_code == 204
    assert client.patch(f'/api/tasks/{task_id}', json={'completed': True}).status_code == 404
    assert client.delete(f'/api/tasks/{task_id}').status_code == 404
    assert len(client.get('/api/tasks').json()) == 1


@pytest.mark.parametrize('payload', [
    {'title': ''}, {'title': '   '}, {'title': 'x' * 201},
    {'title': 'Test', 'priority': 'urgent'}, {'title': 'Test', 'due_date': 'bad'},
    {'title': 'Test', 'description': 'x' * 5001}, {'title': None},
])
def test_invalid_create(client, payload):
    assert client.post('/api/tasks', json=payload).status_code == 422
    assert client.get('/api/tasks').json() == []


def test_invalid_updates_do_not_change_record(client):
    task = client.post('/api/tasks', json={'title': 'Keep me'}).json()
    for patch in [{'title': ' '}, {'title': None}, {'priority': None}, {'completed': None}, {'description': None}]:
        assert client.patch(f'/api/tasks/{task["id"]}', json=patch).status_code == 422
    assert client.get('/api/tasks').json() == [task]
    assert client.get('/api/tasks?status=invalid').status_code == 422
    assert client.get('/api/tasks?sort=invalid').status_code == 422


def test_cors(client):
    result = client.options('/api/tasks', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    assert result.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert 'access-control-allow-origin' not in client.get('/api/tasks', headers={'Origin': 'https://unknown.example'}).headers
