import uuid
from datetime import date, datetime
from datetime import timezone as dtz

import pytest
from core.models import Pet, Profile
from core.services import today
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 5, 13, tzinfo=dtz.utc)

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)
    user = get_user_model().objects.create_user('fitness')
    Profile.objects.create(user=user, timezone='UTC')
    today(user)
    pet = Pet.objects.get(user=user)
    pet.fitness_started_on = date(2026, 10, 1)
    pet.save()
    client = APIClient()
    client.force_authenticate(user)
    return user, client

@pytest.mark.parametrize('steps,delta', [(0,-10),(499,-10),(500,0),(999,0),(1000,10),(4999,10),(5000,30),(8000,30),(None,0)])
def test_step_thresholds(setup, steps, delta):
    user, client = setup
    r = client.post('/api/health/sync/', {'generation':1,'days':[{'date':'2026-10-01','steps':steps}]}, format='json')
    assert r.status_code == 200
    assert r.data['pet']['fitness'] == 50 + delta
    assert r.data['health']['last_step_settlement_date'] == date(2026,10,1)

@pytest.mark.parametrize('minutes,delta', [(0,-10),(299,-10),(300,0),(479,0),(480,10),(600,10),(None,0)])
def test_sleep_thresholds(setup, minutes, delta):
    _, client = setup
    r = client.post('/api/health/sync/', {'generation':1,'days':[{'date':'2026-10-01','sleep_minutes':minutes}]}, format='json')
    assert r.status_code == 200 and r.data['pet']['fitness'] == 50 + delta


def test_preview_is_not_settled_until_window_ends(setup, monkeypatch):
    user, client = setup
    Pet.objects.filter(user=user).update(fitness_started_on=date(2026,10,5))
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW.replace(hour=9))
    r = client.post('/api/health/sync/', {'generation':1,'days':[{'date':'2026-10-05','steps':6000,'sleep_minutes':480}]}, format='json')
    assert r.data['pet']['fitness'] == 50
    assert r.data['health']['step_delta_preview'] == 30
    assert r.data['health']['sleep_delta_preview'] == 10
    assert r.data['health']['last_sleep_settlement_date'] is None
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)
    assert today(user)['pet']['fitness'] == 50  # partial morning observation cannot finalize sleep
    r = client.post('/api/health/sync/', {'generation':1,'days':[{'date':'2026-10-05','steps':6000,'sleep_minutes':480}]}, format='json')
    assert r.data['pet']['fitness'] == 60
    assert r.data['health']['last_step_settlement_date'] is None


def test_backfill_sorted_capped_idempotent_and_missing_sleep_is_neutral(setup):
    user, client = setup
    days=[{'date':f'2026-10-0{d}','steps':5000,'sleep_minutes':None} for d in range(1,5)]
    data={'generation':1,'days':list(reversed(days))}
    first=client.post('/api/health/sync/',data,format='json')
    assert first.status_code == 200 and first.data['pet']['fitness'] == 100
    assert client.post('/api/health/sync/',data,format='json').data['pet']['fitness'] == 100
    assert today(user)['health']['last_step_settlement_date'] == date(2026,10,4)
    assert today(user)['health']['last_sleep_settlement_date'] == date(2026,10,4)


@pytest.mark.parametrize("initial", [10, 5])
def test_zero_is_dead_and_positive_later_cannot_revive(setup, initial):
    user, client = setup
    Pet.objects.filter(user=user).update(fitness=initial)
    r=client.post('/api/health/sync/',{'generation':1,'days':[{'date':'2026-10-01','steps':0,'sleep_minutes':None}]},format='json')
    assert r.data['pet']['fitness'] == 0 and r.data['pet']['state'] == 'dead'
    r=client.post('/api/health/sync/',{'generation':1,'days':[{'date':'2026-10-02','steps':0,'sleep_minutes':None},{'date':'2026-10-03','steps':5000,'sleep_minutes':480}]},format='json')
    assert r.data['pet']['fitness'] == 0 and r.data['pet']['state'] == 'dead'
    assert r.data['pet']['died_at'] == Pet.objects.get(user=user).updated_at


def test_dates_do_not_skip_gaps_and_old_or_future_generations_are_rejected(setup):
    user, client=setup
    body={'generation':1,'days':[{'date':'2026-10-02','steps':5000}]}
    assert client.post('/api/health/sync/',body,format='json').data['pet']['fitness'] == 50
    body['days']=[{'date':'2026-10-01','steps':1000}]
    assert client.post('/api/health/sync/',body,format='json').data['pet']['fitness'] == 90
    body['generation']=2
    assert client.post('/api/health/sync/',body,format='json').status_code == 409
    body={'generation':1,'days':[{'date':'2026-10-06','steps':0}]}
    assert client.post('/api/health/sync/',body,format='json').status_code == 400


def test_walk_actions_removed(setup):
    _,client=setup
    for kind in ['walk_start','walk_finish']:
        assert client.post('/api/actions/',{'id':str(uuid.uuid4()),'generation':1,'kind':kind,'payload':{}},format='json').status_code == 400
