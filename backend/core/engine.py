"""Pure rules: no database, network or model-generated state changes."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PetState:
    updated_at: datetime
    hunger: int = 70
    hydration: int = 70
    energy: int = 70
    bond: int = 10
    xp: int = 0
    level: int = 1
    state: str = "healthy"
    critical_since: datetime | None = None
    water_zero_since: datetime | None = None
    last_decay_at: datetime | None = None
    rest_at: datetime | None = None
    died_at: datetime | None = None
    fitness: int = 50
    mood: int = 70
    sleep_deprived_until: datetime | None = None


def clamp(value):
    return max(0, min(100, int(value)))


def visual_state(pet):
    if pet.state == "dead":
        return "dead"
    if pet.fitness < 20:
        return "sick"
    if min(pet.hunger, pet.hydration) == 0:
        return "angry"
    if (min(pet.hunger, pet.hydration, pet.energy) < 30 or pet.mood < 40
            or (pet.sleep_deprived_until and pet.updated_at < pet.sleep_deprived_until)):
        return "sad"
    return "happy" if pet.mood >= 70 and min(pet.hunger, pet.hydration, pet.energy) >= 40 else "normal"


def advance(pet, now):
    pet.fitness = clamp(pet.fitness)
    if pet.state == "dead" or now < pet.updated_at:
        return pet
    pet.last_decay_at = pet.last_decay_at or pet.updated_at
    for stat, clock in [("hunger", "critical_since"), ("hydration", "water_zero_since")]:
        if getattr(pet, stat) > 0:
            setattr(pet, clock, None)
        elif getattr(pet, clock) is None:
            setattr(pet, clock, pet.updated_at)
    while True:
        decay = pet.last_decay_at + timedelta(hours=5)
        deadlines = [t + timedelta(hours=48) for t in [pet.critical_since, pet.water_zero_since] if t]
        rest = pet.rest_at + timedelta(minutes=30) if pet.rest_at else None
        event = min([decay] + deadlines + ([rest] if rest else []))
        if pet.fitness <= 0 or (deadlines and min(deadlines) <= min(event, now)):
            pet.state = "dead"
            pet.died_at = pet.updated_at if pet.fitness <= 0 else min(deadlines)
            pet.rest_at = None
            return pet
        if event > now:
            break
        pet.updated_at = event
        if rest == event:
            pet.energy = clamp(pet.energy + 10)
            pet.rest_at = event if pet.energy < 100 else None
        if decay == event:
            if pet.hunger == 0 or pet.hydration == 0:
                pet.fitness = clamp(pet.fitness - 30)
            for stat, amount in [("hunger", 10), ("hydration", 20), ("energy", 5), ("mood", 5)]:
                setattr(pet, stat, clamp(getattr(pet, stat) - amount))
            pet.last_decay_at = event
            if pet.hunger == 0 and pet.critical_since is None:
                pet.critical_since = event
            if pet.hydration == 0 and pet.water_zero_since is None:
                pet.water_zero_since = event
        if pet.fitness <= 0:
            pet.state = "dead"
            pet.died_at = event
            pet.rest_at = None
            return pet
    pet.updated_at = now
    pet.state = "critical" if min(pet.hunger, pet.hydration) == 0 else "hungry" if pet.hunger < 40 else "healthy"
    return pet


def feed(pet, amount=30):
    if pet.state == "dead":
        raise ValueError("Pet has died; start a new pet")
    if pet.hunger >= 100:
        raise ValueError("Pet is already full")
    pet.hunger = clamp(pet.hunger + amount)
    pet.bond = clamp(pet.bond + 2)
    pet.critical_since = None
    pet.state = "hungry" if pet.hunger < 40 else "healthy"
    gain_xp(pet, 5)


def gain_xp(pet, amount):
    if amount < 0:
        raise ValueError("XP cannot decrease")
    pet.xp += amount
    pet.level = pet.xp // 100 + 1


def evolution(level, study, activity):
    if level < 5:
        return "baby"
    path = (
        "scholar"
        if study > activity * 1.2
        else ("explorer" if activity > study * 1.2 else "guardian")
    )
    return (
        {"scholar": "sage", "explorer": "adventurer", "guardian": "spirit"}[path]
        if level >= 10
        else path
    )
