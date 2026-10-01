import pytest
from core import ai
from core.models import Profile
from core.services import today
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db


def test_structured_output_rejects_unknown_action_and_long_text():
    with pytest.raises(ValueError):
        ai.validate_reply(
            {
                "emotion": "happy",
                "message": "Hi",
                "suggested_action": "delete_account",
                "urgency": "low",
            }
        )
    with pytest.raises(ValueError):
        ai.validate_reply(
            {"emotion": "happy", "message": "x" * 161, "suggested_action": "none", "urgency": "low"}
        )


def test_health_excluded_without_separate_consent():
    user = get_user_model().objects.create_user("alice")
    ctx = ai.build_context(user, "Hello")
    assert "health" not in ctx
    assert "energy" not in ctx["pet"]
    Profile.objects.filter(user=user).update(ai_health_consent=True)
    assert "health" in ai.build_context(user, "Hello")


def test_vector_retrieval_is_scoped_and_deletion_works():
    a = get_user_model().objects.create_user("alice")
    b = get_user_model().objects.create_user("bob")
    today(a)
    Profile.objects.filter(user=a).update(memory_enabled=True)
    own = ai.save_memory(a, "Japanese study after dinner", "routine")
    ai.save_memory(b, "Japanese study after dinner every day", "routine")
    found = ai.retrieve(a, "Japanese study dinner", 3)
    assert [m.id for m in found] == [own.id]
    own.delete()
    assert ai.retrieve(a, "Japanese study dinner", 3) == []


def test_provider_failure_degrades_without_state_mutation(monkeypatch, settings):
    user = get_user_model().objects.create_user("alice")
    before = today(user)
    settings.AI_MODE = "live"

    def fail(*args, **kwargs):
        raise TimeoutError("simulated provider timeout")

    monkeypatch.setattr(ai, "completion", fail)
    result = ai.respond(user, "Hello")
    assert result["source"] == "fallback"
    assert result["suggested_action"] in ai.ACTIONS
    assert today(user)["pet"]["xp"] == before["pet"]["xp"]


def test_demo_memory_extraction_only_explicit_remember():
    assert ai.extract_candidate("hello there") is None
    assert ai.extract_candidate("Remember: I like studying Japanese after dinner")["content"] == "I like studying Japanese after dinner"


def test_retrieval_can_abstain_when_all_memories_are_unrelated():
    user = get_user_model().objects.create_user("abstention")
    today(user)
    Profile.objects.filter(user=user).update(memory_enabled=True)
    ai.save_memory(user, "blue violet painting", "preference")
    assert ai.retrieve(user, "Japanese dinner coding", 3) == []


def test_english_replies_for_demo_and_failure(settings, monkeypatch):
    user = get_user_model().objects.create_user('english_pet')
    settings.AI_MODE = 'demo'
    demo = ai.respond(user, 'Hello')
    assert demo['message'].isascii()
    assert 0 < len(demo['message']) <= 160
    settings.AI_MODE = 'live'
    def fail(*args, **kwargs):
        raise TimeoutError('provider unavailable')
    monkeypatch.setattr(ai, 'completion', fail)
    fallback = ai.respond(user, 'Hello')
    assert fallback['message'].isascii()
    assert fallback['source'] == 'fallback'
