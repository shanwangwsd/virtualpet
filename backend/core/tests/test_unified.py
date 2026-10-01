import uuid
from datetime import datetime, timedelta, timezone

import pytest
from core import engine
from core.models import Pet
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

T = datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_five_hour_decay_and_single_penalty():
    p = engine.PetState(updated_at=T, hunger=10, hydration=20)
    engine.advance(p, T + timedelta(hours=5))
    assert (p.hunger, p.hydration, p.energy, p.mood, p.fitness) == (0, 0, 65, 65, 50)
    engine.advance(p, T + timedelta(hours=9, minutes=59))
    assert p.fitness == 50
    engine.advance(p, T + timedelta(hours=10))
    assert p.fitness == 20
    engine.advance(p, T + timedelta(hours=15))
    assert p.fitness == 0 and p.state == 'dead'
    assert p.died_at == T + timedelta(hours=15)


@pytest.mark.parametrize('field', ['critical_since', 'water_zero_since'])
def test_independent_48_hour_deadline(field):
    p = engine.PetState(updated_at=T)
    setattr(p, field, T - timedelta(hours=48))
    if field == 'critical_since':
        p.hunger = 0
    else:
        p.hydration = 0
    engine.advance(p, T)
    assert p.state == 'dead' and p.died_at == T


def test_visual_priority_and_recovery():
    p = engine.PetState(updated_at=T)
    assert engine.visual_state(p) == 'happy'
    p.hunger = 0
    assert engine.visual_state(p) == 'angry'
    p.fitness = 10
    assert engine.visual_state(p) == 'sick'
    p.state = 'dead'
    assert engine.visual_state(p) == 'dead'


@pytest.mark.django_db
def test_reward_choice_retry_use_age_and_rebirth():
    user = get_user_model().objects.create_user('unified', password='long-password')
    c = APIClient()
    c.force_authenticate(user)
    first = c.get('/api/today/').data
    h = c.post('/api/habits/', {'name': 'Daily goal', 'target': 1}, format='json').data
    def action(kind, payload=None, operation=None, generation=1):
        return c.post('/api/actions/', {'id': operation or str(uuid.uuid4()), 'kind': kind, 'generation': generation, 'payload': payload or {}}, format='json')
    done = action('complete', {'habit_id': h['id']})
    assert done.status_code == 200
    assert done.data['inventory']['items'] == []
    reward = done.data['pending_rewards'][0]['id']
    op = str(uuid.uuid4())
    claim = action('claim_reward', {'reward_id': reward, 'category': 0}, op)
    assert claim.status_code == 200
    assert action('claim_reward', {'reward_id': reward, 'category': 0}, op).data == claim.data
    assert action('claim_reward', {'reward_id': reward, 'category': 1}).status_code == 409
    item = claim.data['inventory']['items'][0]
    assert item['quantity'] == 1 and item['category'] == 'food'
    used = action('use_item', {'item_id': item['id']})
    assert used.status_code == 200 and used.data['pet']['hunger'] > first['pet']['hunger']
    assert action('use_item', {'item_id': item['id']}).status_code == 409
    pet = Pet.objects.get(user=user)
    pet.initial_age_days = 999
    pet.save()
    assert c.get('/api/today/').data['pet']['age_days'] == 0
    pet.fitness = 0
    pet.state = 'dead'
    pet.save()
    new = action('rebirth')
    assert new.status_code == 200
    assert new.data['pet']['fitness'] == 50 and new.data['pet']['age_days'] == 0


def test_rest_and_rescue_reset_only_the_relevant_clock():
    p = engine.PetState(updated_at=T, energy=50, rest_at=T, hunger=0, hydration=0,
                        critical_since=T, water_zero_since=T)
    engine.advance(p, T + timedelta(minutes=29))
    assert p.energy == 50
    engine.advance(p, T + timedelta(minutes=30))
    assert p.energy == 60
    engine.feed(p, 15)
    assert p.critical_since is None and p.water_zero_since == T


@pytest.mark.django_db
def test_full_stats_do_not_consume_items_and_toys_raise_mood():
    from core.models import InventoryItem
    from core.services import apply_action, today
    from rest_framework.exceptions import APIException
    user = get_user_model().objects.create_user('toys')
    today(user)
    InventoryItem.objects.create(user=user, item_id=4, quantity=1)
    Pet.objects.filter(user=user).update(mood=100)
    op = {'id': uuid.uuid4(), 'generation': 1, 'kind': 'use_item', 'payload': {'item_id': 4}}
    with pytest.raises(APIException):
        apply_action(user, op)
    assert InventoryItem.objects.get(user=user).quantity == 1
    Pet.objects.filter(user=user).update(mood=40)
    result = apply_action(user, op)
    assert result['pet']['mood'] == 55
    assert InventoryItem.objects.get(user=user).quantity == 0


@pytest.mark.django_db
def test_personality_and_health_consent_in_care_context(settings):
    from core import ai
    from core.models import Profile
    from core.services import today
    settings.AI_MODE = 'demo'
    user = get_user_model().objects.create_user('personality')
    today(user)
    profile = Profile.objects.get(user=user)
    responses = set()
    for personality in ai.PERSONALITIES:
        profile.personality = personality
        profile.save()
        context = ai.build_context(user, 'water', mode='none')
        assert 'hydration' in context['pet'] and 'mood' in context['pet']
        assert 'fitness' not in context['pet'] and 'health' not in context
        responses.add(ai.generate(context)['message'])
    assert len(responses) == 5
    profile.ai_health_consent = True
    profile.save()
    context = ai.build_context(user, 'water', mode='none')
    assert {'fitness', 'energy', 'mood', 'hunger', 'hydration', 'visual_state'} <= context['pet'].keys()


@pytest.mark.django_db
def test_reaction_requires_owned_care_and_caches_demo_only(settings):
    settings.AI_MODE = 'demo'
    user = get_user_model().objects.create_user('reaction')
    c = APIClient()
    c.force_authenticate(user)
    op = str(uuid.uuid4())
    assert c.post('/api/actions/', {'id': op, 'generation': 1, 'kind': 'water'}, format='json').status_code == 200
    first = c.post('/api/pet/reaction/', {'action_id': op}, format='json')
    assert first.status_code == 200 and first.data['source'] == 'demo'
    assert c.post('/api/pet/reaction/', {'action_id': op}, format='json').data == first.data
    c.force_authenticate(get_user_model().objects.create_user('outsider'))
    assert c.post('/api/pet/reaction/', {'action_id': op}, format='json').status_code == 404


@pytest.mark.django_db(transaction=True)
def test_concurrent_reward_claim_only_grants_one_item():
    from concurrent.futures import ThreadPoolExecutor

    from core.models import Habit, InventoryItem
    from core.services import apply_action
    from django.db import close_old_connections
    user = get_user_model().objects.create_user('reward_race')
    habit = Habit.objects.create(user=user, name='Goal', target=1)
    done = apply_action(user, {'id': uuid.uuid4(), 'generation': 1, 'kind': 'complete', 'payload': {'habit_id': habit.id}})
    reward = done['pending_rewards'][0]['id']
    def claim(category):
        close_old_connections()
        try:
            apply_action(user, {'id': uuid.uuid4(), 'generation': 1, 'kind': 'claim_reward', 'payload': {'reward_id': reward, 'category': category}})
            return 200
        except Exception as exc:
            return getattr(exc, 'status_code', 500)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, [0, 1])) == [200, 409]
    assert sum(InventoryItem.objects.filter(user=user).values_list('quantity', flat=True)) == 1


@pytest.mark.django_db
def test_saved_care_replays_before_advancing_to_reconnect_time(monkeypatch):
    from core.services import apply_action, today
    monkeypatch.setattr('django.utils.timezone.now', lambda: T)
    user = get_user_model().objects.create_user('offline_care')
    today(user)
    Pet.objects.filter(user=user).update(hunger=100, hydration=20)
    monkeypatch.setattr('django.utils.timezone.now', lambda: T + timedelta(hours=16))
    first = apply_action(user, {'id': uuid.uuid4(), 'generation': 1, 'kind': 'water', 'occurred_at': T + timedelta(hours=4), 'payload': {}})
    assert first['pet']['state'] != 'dead'
    apply_action(user, {'id': uuid.uuid4(), 'generation': 1, 'kind': 'rest', 'occurred_at': T + timedelta(hours=6), 'payload': {}})
    final = today(user)['pet']
    assert final['state'] != 'dead' and final['fitness'] == 20


@pytest.mark.django_db
def test_care_reaction_describes_the_actual_item(monkeypatch):
    from core import ai
    from core.models import InventoryItem
    from core.services import apply_action, today
    user = get_user_model().objects.create_user('specific_reaction')
    today(user)
    InventoryItem.objects.create(user=user, item_id=3, quantity=1)
    operation = uuid.uuid4()
    apply_action(user, {'id': operation, 'generation': 1, 'kind': 'use_item', 'payload': {'item_id': 3}})
    seen = []
    def response(user, message, mode):
        seen.append(message)
        return {'emotion': 'happy', 'message': 'Yum!', 'suggested_action': 'none', 'urgency': 'low', 'source': 'demo'}
    monkeypatch.setattr(ai, 'respond', response)
    c = APIClient()
    c.force_authenticate(user)
    assert c.post('/api/pet/reaction/', {'action_id': str(operation)}, format='json').status_code == 200
    assert 'Meal' in seen[0] and 'food' in seen[0]


@pytest.mark.django_db
def test_pending_reward_identifies_its_habit_even_with_duplicate_names():
    from core.models import Habit
    from core.services import apply_action
    user = get_user_model().objects.create_user('reward_link')
    first = Habit.objects.create(user=user, name='Same name', target=1)
    second = Habit.objects.create(user=user, name='Same name', target=1)
    for habit in [first, second]:
        result = apply_action(user, {'id': uuid.uuid4(), 'generation': 1, 'kind': 'complete', 'payload': {'habit_id': habit.id}})
    assert {r['habit_id'] for r in result['pending_rewards']} == {first.id, second.id}


@pytest.mark.django_db
def test_schedule_speech_uses_personality_and_task_without_memory(monkeypatch):
    from core import ai
    from core.models import Profile
    from core.services import today
    user = get_user_model().objects.create_user('schedule_voice')
    today(user)
    Profile.objects.filter(user=user).update(personality='tsundere')
    seen = []
    def generate(context):
        seen.append(context)
        return {'emotion': 'happy', 'message': 'Hmph! Japanese time. Impress me with a sentence!', 'suggested_action': 'habits', 'urgency': 'low', 'source': 'live'}
    monkeypatch.setattr(ai, 'generate', generate)
    c = APIClient()
    c.force_authenticate(user)
    response = c.post('/api/schedule/speech/', {'title': 'Study Japanese', 'hour': 19, 'minute': 0}, format='json')
    assert response.status_code == 200
    assert seen[0]['personality'] == 'tsundere'
    assert seen[0]['schedule']['title'] == 'Study Japanese'
    assert 'memories' not in seen[0] and 'recent' not in seen[0]
    assert c.post('/api/schedule/speech/', {'title': '', 'hour': 19, 'minute': 0}, format='json').status_code == 400


@pytest.mark.django_db
def test_schedule_speech_failure_still_returns_task_specific_fallback(monkeypatch):
    from core import ai
    user = get_user_model().objects.create_user('schedule_fallback')
    def fail(context):
        raise TimeoutError('unavailable')
    monkeypatch.setattr(ai, 'generate', fail)
    c = APIClient()
    c.force_authenticate(user)
    response = c.post('/api/schedule/speech/', {'title': 'Read', 'hour': 20, 'minute': 0}, format='json')
    assert response.status_code == 200
    assert 'Read' in response.data['message'] and response.data['source'] == 'fallback'


@pytest.mark.parametrize('initial', [30, 20])
def test_decay_reaching_zero_kills_without_negative_fitness(initial):
    p = engine.PetState(updated_at=T, hunger=0, fitness=initial)
    engine.advance(p, T + timedelta(hours=5))
    assert p.fitness == 0 and p.state == 'dead'
    assert p.died_at == T + timedelta(hours=5)


def test_existing_zero_fitness_dies_immediately():
    p = engine.PetState(updated_at=T, fitness=0)
    engine.advance(p, T)
    assert p.state == 'dead' and p.died_at == T
