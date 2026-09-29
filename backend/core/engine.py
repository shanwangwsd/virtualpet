"""Pure rules: no database, network or model-generated state changes."""

import math
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


def clamp(value):
    return max(0, min(100, int(value)))


def advance(pet, now):
    if pet.state == "dead" or now < pet.updated_at:
        return pet
    periods = int((now - pet.updated_at).total_seconds() // 14400)
    if pet.hunger == 0 and pet.critical_since is None:
        pet.critical_since = pet.updated_at
    if periods:
        if pet.hunger > 0 and periods * 5 >= pet.hunger:
            pet.critical_since = pet.updated_at + timedelta(hours=4 * math.ceil(pet.hunger / 5))
        pet.hunger = clamp(pet.hunger - periods * 5)
        pet.hydration = clamp(pet.hydration - periods * 5)
        pet.updated_at += timedelta(hours=4 * periods)
    if pet.critical_since and now - pet.critical_since >= timedelta(hours=48):
        pet.state = "dead"
    else:
        pet.state = (
            "critical"
            if pet.hunger == 0
            else (
                "very_hungry" if pet.hunger < 20 else ("hungry" if pet.hunger < 40 else "healthy")
            )
        )
    return pet


def feed(pet):
    if pet.state == "dead":
        raise ValueError("Pet has died; rebirth is required")
    if pet.hunger >= 100:
        raise ValueError("Pet is already full")
    pet.hunger = clamp(pet.hunger + 30)
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


def mood(pet, steps_bonus=0, habit_count=0, fed=False, interaction_bonus=0):
    return clamp(
        50
        + steps_bonus
        + min(habit_count * 5, 15)
        + (5 if fed else 0)
        + min(interaction_bonus, 15)
        - (30 if pet.hunger == 0 else 0)
        - (10 if pet.energy < 50 else 0)
    )
