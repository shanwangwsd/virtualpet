import uuid
from datetime import timedelta

import pytest
from core.models import Daily, Habit, HabitLog, InventoryItem, Pet, RewardLedger
from core.services import today
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    user = get_user_model().objects.create_user('pet_details')
    today(user)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


def test_identity_changes_preserve_progress_and_age_is_automatic(owner):
    user, client = owner
    Pet.objects.filter(user=user).update(xp=135, level=2, hunger=65)
    response = client.patch('/api/pet/', {'generation': 1, 'name': 'Clover', 'species': 'potato', 'personality': 'calm'}, format='json')
    assert response.status_code == 200
    pet = response.data['pet']
    assert (pet['name'], pet['species'], pet['age_days']) == ('Clover', 'potato', 0)
    assert response.data['personality'] == 'calm'
    assert (pet['xp'], pet['level'], pet['hunger']) == (135, 2, 65)
    changed = client.patch('/api/pet/', {'generation': 1, 'species': 'cat'}, format='json')
    assert changed.status_code == 200 and changed.data['pet']['age_days'] == 0
    assert changed.data['pet']['xp'] == 135
    assert client.patch('/api/pet/', {'generation': 1, 'initial_age_days': 10}, format='json').status_code == 400


@pytest.mark.parametrize('field,value', [('species', 'dragon'), ('gender', 'invalid'), ('initial_age_days', -1), ('initial_age_days', 3651), ('name', '   ')])
def test_invalid_identity_is_rejected(owner, field, value):
    _, client = owner
    assert client.patch('/api/pet/', {'generation': 1, field: value}, format='json').status_code == 400


def test_configuration_is_owner_scoped_and_rejects_stale_generation(owner):
    user, client = owner
    other = get_user_model().objects.create_user('other_pet')
    today(other)
    assert client.patch('/api/pet/', {'generation': 2, 'name': 'Wrong'}, format='json').status_code == 409
    assert client.patch('/api/pet/', {'generation': 1, 'name': 'Pip', 'species': 'cat'}, format='json').status_code == 200
    assert Pet.objects.get(user=other).name == 'Mochi'
    assert Pet.objects.get(user=user).name == 'Pip'


def test_age_grows_each_24_hours_without_changing_level(owner):
    user, client = owner
    now = timezone.now()
    Pet.objects.filter(user=user).update(born_at=now-timedelta(hours=47), updated_at=now)
    pet = today(user)['pet']
    assert pet['age_days'] == 1 and pet['level'] == 1
    Pet.objects.filter(user=user).update(born_at=now-timedelta(hours=48, minutes=1))
    assert today(user)['pet']['age_days'] == 2


def test_daily_care_bonus_crosses_level_once_and_retries_do_not_duplicate(owner):
    user, client = owner
    Pet.objects.filter(user=user).update(hunger=65, xp=90)
    InventoryItem.objects.create(user=user, item_id=1, quantity=3)
    Daily.objects.filter(user=user).update(care_bonus_claimed=False)
    RewardLedger.objects.filter(user=user, source__startswith="care:").delete()
    complete_three(user)
    operation = {'id': str(uuid.uuid4()), 'kind': 'use_item', 'generation': 1, 'payload': {'item_id': 1}}
    first = client.post('/api/actions/', operation, format='json')
    assert first.status_code == 200
    assert first.data['pet']['mood'] >= 70
    assert (first.data['pet']['xp'], first.data['pet']['level']) == (100, 2)
    assert first.data['care_bonus_claimed'] is True
    assert client.post('/api/actions/', operation, format='json').data == first.data
    assert today(user)['pet']['xp'] == 100
    operation['id'] = str(uuid.uuid4())
    assert client.post('/api/actions/', operation, format='json').data['pet']['xp'] == 105
    operation['id'] = str(uuid.uuid4())
    assert client.post('/api/actions/', operation, format='json').status_code == 200
    operation['id'] = str(uuid.uuid4())
    assert client.post('/api/actions/', operation, format='json').status_code == 409
    assert Pet.objects.get(user=user).xp == 110


def test_bonus_requires_both_fullness_and_mood_and_resets_next_day(owner, monkeypatch):
    user, _ = owner
    Daily.objects.filter(user=user).update(care_bonus_claimed=False)
    RewardLedger.objects.filter(user=user, source__startswith="care:").delete()
    Pet.objects.filter(user=user).update(hunger=69, xp=0, mood=70)
    assert today(user)['pet']['xp'] == 0
    Pet.objects.filter(user=user).update(hunger=70)
    assert today(user)['pet']['xp'] == 5
    now = timezone.now()
    Pet.objects.filter(user=user).update(hunger=100, updated_at=now)
    monkeypatch.setattr("core.services.timezone.now", lambda: now + timedelta(days=1))
    Pet.objects.filter(user=user).update(hunger=100, hydration=100, mood=70, updated_at=now+timedelta(days=1), last_decay_at=now+timedelta(days=1))
    assert today(user)['pet']['xp'] == 10


def test_rebirth_preserves_identity_but_starts_new_age_and_growth(owner):
    user, client = owner
    assert client.patch('/api/pet/', {'generation': 1, 'species': 'potato'}, format='json').status_code == 200
    Pet.objects.filter(user=user).update(state='dead', died_at=timezone.now())
    response = client.post('/api/actions/', {'id': str(uuid.uuid4()), 'kind': 'rebirth', 'generation': 1, 'payload': {}}, format='json')
    pet = response.data['pet']
    assert (pet['species'], pet['age_days'], pet['level']) == ('potato', 0, 1)


def complete_three(user, day=None):
    day = day or today(user)["date"]
    for i in range(3):
        habit, _ = Habit.objects.get_or_create(user=user, name=f"Care habit {i}", defaults={"target": 1})
        HabitLog.objects.update_or_create(habit=habit, date=day, defaults={"progress": 1, "completed": True, "reward_claimed": True})
