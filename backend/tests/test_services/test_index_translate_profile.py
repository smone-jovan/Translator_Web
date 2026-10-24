import pytest

from database import LorebookEntry, Thread
from services.ai.chunking import maybe_chunk
from services.ai.index_translate import (
    build_index_translate_messages,
    build_index_translate_prompt,
    clean_index_title_output,
    collect_glossary_pairs,
    is_index_translate_model,
)
from services.ai.lm_studio import LMStudioAdapter


class TestModelDetection:
    @pytest.mark.parametrize(
        "name",
        [
            "IndexTeam/Index-Translate-2B-GGUF",
            "index-translate-2b",
            "indexteam/index-translate-9b@q4_k_m",
            "Index_Translate_9B",
            "indextranslate-2b",
        ],
    )
    def test_detects_index_translate_models(self, name):
        assert is_index_translate_model(name)

    @pytest.mark.parametrize("name", [None, "", "gemma-3-4b", "translategemma-4b-it", "Index-Homura-2B"])
    def test_ignores_other_models(self, name):
        assert not is_index_translate_model(name)


class TestPrompt:
    def test_plain_prompt_matches_readme_template_for_indonesian(self):
        assert build_index_translate_prompt("  你好  ", "Indonesian") == (
            "请将以下文本翻译为印尼语，直接输出翻译结果，不要进行任何解释。\n\n你好"
        )

    def test_non_indonesian_target_falls_back_to_english(self):
        assert build_index_translate_prompt("你好", "English").startswith("请将以下文本翻译为英语，")

    def test_glossary_uses_canonical_insttrans_format(self):
        prompt = build_index_translate_prompt(
            "林动来了", "Indonesian", glossary=[("林动", "Lin Dong"), ("青檀", "Qing Tan")]
        )
        assert prompt == (
            "请将以下小说翻译成印尼语，并且严格遵循所有约束要求。\n\n"
            "【源文】\n林动来了\n\n"
            "【约束要求】\n1. 【硬性要求】专名/术语对照: 林动→Lin Dong、青檀→Qing Tan\n\n"
            "只输出译文，不要有任何额外说明。"
        )

    def test_messages_are_a_single_user_message_without_system_prompt(self):
        messages = build_index_translate_messages("你好", "Indonesian")
        assert messages == [{"role": "user", "content": build_index_translate_prompt("你好", "Indonesian")}]


class TestCleanTitleOutput:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Penguasa Misteri", "Penguasa Misteri"),
            ("  \"Penguasa Misteri\"  ", "Penguasa Misteri"),
            ("<think>\nhmm\n</think>\n\nPenguasa Misteri", "Penguasa Misteri"),
            ("[BOOK_TITLE]: Penguasa Misteri", "Penguasa Misteri"),
            ("[CHAPTER_3]: Bab 1: Awal", "Bab 1: Awal"),
            ("Penguasa Misteri\n\nCatatan: ini terjemahan", "Penguasa Misteri"),
            ("", ""),
        ],
    )
    def test_reduces_model_output_to_a_single_title_line(self, raw, expected):
        assert clean_index_title_output(raw) == expected


class TestGlossaryCollection:
    def _thread(self, db):
        thread = Thread(title="t")
        db.add(thread)
        db.commit()
        return thread

    def test_only_terms_present_in_text_are_returned(self, db_session):
        thread = self._thread(db_session)
        db_session.add_all([
            LorebookEntry(thread_id=thread.id, original_term="林动", translated_term="Lin Dong"),
            LorebookEntry(thread_id=thread.id, original_term="青檀", translated_term="Qing Tan"),
        ])
        db_session.commit()
        assert collect_glossary_pairs(db_session, thread.id, "林动笑了") == [("林动", "Lin Dong")]

    def test_archived_entries_are_skipped(self, db_session):
        thread = self._thread(db_session)
        db_session.add(
            LorebookEntry(thread_id=thread.id, original_term="林动", translated_term="Lin Dong", is_archived=True)
        )
        db_session.commit()
        assert collect_glossary_pairs(db_session, thread.id, "林动笑了") == []

    def test_no_thread_returns_empty(self, db_session):
        assert collect_glossary_pairs(db_session, None, "林动笑了") == []

    def test_limit_keeps_longest_terms_first(self, db_session):
        thread = self._thread(db_session)
        db_session.add_all([
            LorebookEntry(thread_id=thread.id, original_term="林", translated_term="Lin"),
            LorebookEntry(thread_id=thread.id, original_term="林动之父", translated_term="Ayah Lin Dong"),
        ])
        db_session.commit()
        assert collect_glossary_pairs(db_session, thread.id, "林动之父说林", limit=1) == [
            ("林动之父", "Ayah Lin Dong")
        ]


class FakeProvider:
    translation_temperature = 0.0
    translation_chunk_chars = 20

    def __init__(self):
        self.calls = []

    async def chat_completion(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        return f"T{len(self.calls)}"

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        self.calls.append(messages)
        yield f"T{len(self.calls)}"


class TestChunkingWithPromptBuilder:
    SOURCE = "aaaaaaaa\nbbbbbbbb\ncccccccc\ndddddddd"

    def _builder(self, text):
        return build_index_translate_messages(text, "Indonesian")

    @pytest.mark.asyncio
    async def test_each_chunk_gets_its_own_complete_prompt(self):
        inner = FakeProvider()
        provider = maybe_chunk(inner, source_text=self.SOURCE, message_builder=self._builder)
        result = await provider.chat_completion(self._builder(self.SOURCE))
        assert len(inner.calls) == 2
        for call in inner.calls:
            assert len(call) == 1
            assert call[0]["content"].startswith("请将以下文本翻译为印尼语，")
            assert len(call[0]["content"].split("\n\n", 1)[1]) <= 20
        assert result == "T1\n\nT2"

    @pytest.mark.asyncio
    async def test_other_message_shapes_pass_through(self):
        inner = FakeProvider()
        provider = maybe_chunk(inner, source_text=self.SOURCE, message_builder=self._builder)
        continuation = self._builder(self.SOURCE) + [
            {"role": "assistant", "content": "... tail"},
            {"role": "user", "content": "continue"},
        ]
        await provider.chat_completion(continuation)
        assert inner.calls == [continuation]

    @pytest.mark.asyncio
    async def test_short_source_is_not_split(self):
        inner = FakeProvider()
        provider = maybe_chunk(inner, source_text="aaa", message_builder=self._builder)
        messages = self._builder("aaa")
        await provider.chat_completion(messages)
        assert inner.calls == [messages]


class TestAdapterOptions:
    def test_thinking_is_disabled_for_index_translate(self):
        adapter = LMStudioAdapter(model="IndexTeam/Index-Translate-2B-GGUF")
        assert adapter._extra_payload() == {"chat_template_kwargs": {"enable_thinking": False}}

    def test_other_models_get_no_extra_payload(self):
        assert LMStudioAdapter(model="gemma-3-4b")._extra_payload() == {}
        assert LMStudioAdapter()._extra_payload() == {}
