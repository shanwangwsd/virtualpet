from datetime import datetime, timedelta, timezone

import pytest
from core.engine import PetState, advance, evolution, feed, gain_xp

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_decay_retains_partial_period_and_is_idempotent():
    pet = PetState(updated_at=T)
    advance(pet, T + timedelta(hours=5))
    assert pet.hunger == 60
    advance(pet, T + timedelta(hours=7))
    assert pet.hunger == 60
    advance(pet, T + timedelta(hours=10))
    assert pet.hunger == 50


def test_death_uses_actual_crossing_time_not_refresh_time():
    pet = PetState(hunger=5, updated_at=T)
    advance(pet, T + timedelta(hours=53))
    assert pet.critical_since == T + timedelta(hours=5)
    assert pet.state == "dead"


def test_feed_rescues_critical_pet_and_caps_values():
    pet = PetState(hunger=0, bond=99, critical_since=T, updated_at=T)
    feed(pet)
    assert (pet.hunger, pet.bond, pet.xp, pet.critical_since) == (30, 100, 5, None)


def test_dead_pet_cannot_be_fed():
    with pytest.raises(ValueError):
        feed(PetState(state="dead", updated_at=T))


def test_xp_and_evolution():
    pet = PetState(xp=95, updated_at=T)
    gain_xp(pet, 10)
    assert pet.level == 2
    assert evolution(5, 20, 2) == "scholar"
    assert evolution(10, 2, 20) == "adventurer"
    assert evolution(5, 10, 10) == "guardian"


def test_no_negative_time_decay():
    pet = PetState(updated_at=T)
    advance(pet, T - timedelta(days=1))
    assert pet.hunger == 70
