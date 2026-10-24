from services.ai.lm_studio import LMStudioAdapter
from services.ai.openai import OpenAIAdapter


def test_lm_studio_translates_greedy():
    assert LMStudioAdapter().translation_temperature == 0.0


def test_other_providers_keep_default_translation_temperature():
    assert OpenAIAdapter.translation_temperature == 0.3
