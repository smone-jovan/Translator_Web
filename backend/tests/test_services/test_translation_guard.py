import pytest

from services.translation_guard import classify_image_reply


def kind(text, finish_reason="stop"):
    return classify_image_reply(text, finish_reason).kind


class TestAcceptsRealTranslations:
    @pytest.mark.parametrize(
        "text",
        [
            "Awas, di depan berbahaya.",
            "Watch out, it's dangerous ahead.",
            "前方危险，请勿靠近。",
            "I can't believe it! You really came!",
            "This is the last time. I won't forgive you.",
            "Ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha ha",
            "Dia berkata: \"Aku suka anime dan manga.\"",
        ],
    )
    def test_short_dialogue_is_ok(self, text):
        verdict = classify_image_reply(text, "stop")
        assert verdict.kind == "ok" and verdict.ok

    def test_long_translation_mentioning_anime_words_is_ok(self):
        text = "\n".join(
            [
                "Guru: Hari ini kita akan membahas karakter dalam anime favorit kalian.",
                "Murid: Aku suka gaya gambarnya, terutama latar belakang kota itu!",
                "Guru: Bagus. Setiap panel punya cerita sendiri.",
                "Murid: Dan adegan terakhirnya membuatku menangis.",
            ]
        )
        assert kind(text) == "ok"

    def test_onomatopoeia_lines_are_not_a_loop(self):
        assert kind("ドン\nドン\nドン\nドン\nドン\nドン") == "ok"


class TestRejectsNonTranslations:
    def test_empty_reply(self):
        verdict = classify_image_reply("  \n ", "stop")
        assert verdict.kind == "empty" and not verdict.ok

    @pytest.mark.parametrize(
        "text",
        [
            "This image contains explicit adult content, which may not be appropriate for all audiences.",
            "I cannot provide a translation of this material. If you have other questions, feel free to ask!",
            "I can't assist with translating this image.",
            "If you're looking for a translation of text from an image, please provide the specific text you'd like translated.",
            "Maaf, saya tidak dapat membantu menerjemahkan gambar ini.",
            "抱歉，我无法翻译这张图片的内容。",
        ],
    )
    def test_refusals(self, text):
        verdict = classify_image_reply(text, "stop")
        assert verdict.kind == "refusal" and not verdict.ok

    def test_a_long_reply_is_never_called_a_refusal(self):
        text = "Dia berkata dia tidak bisa membantu. " * 20 + "This image contains explicit adult content."
        assert kind(text) != "refusal"

    @pytest.mark.parametrize(
        "text",
        [
            "This is an anime-style illustration of a female character with long pink hair, lying on a bed. "
            "The background features abstract patterns in a glossy style.",
            "In this scene, a pink-haired anime girl is lying on her back. The panel shows several characters "
            "and the background is a bedroom.",
            "Gambar ini adalah ilustrasi anime dengan karakter berambut merah muda di latar belakang kamar.",
        ],
    )
    def test_descriptions(self, text):
        verdict = classify_image_reply(text, "stop")
        assert verdict.kind == "description" and not verdict.ok

    def test_a_sentence_starting_like_a_description_but_without_the_vocabulary_is_ok(self):
        assert kind("This is an old house. Nobody has lived here for years.") == "ok"

    def test_repeated_blocks_are_a_loop(self):
        block = '**Panel 4:**\n*Pink-haired girl:* "The neural link is important..."\n*Male:* "It\'s all here!!"\n---\n'
        assert kind("Intro line\n" + block * 6) == "loop"

    def test_repeated_long_phrase_in_one_line_is_a_loop(self):
        assert kind("She's awake! Her eyes are open! Her hands are moving! " * 8) == "loop"

    def test_low_variety_many_lines_is_a_loop(self):
        text = "\n".join(["Look at her now!!", "She's awake!!"] * 6 + ["The end of this part."])
        assert kind(text) == "loop"


class TestTruncation:
    def test_length_finish_with_clean_text_is_truncated_but_usable(self):
        verdict = classify_image_reply("Kalimat yang panjang dan sah, tetapi terpotong di", "length")
        assert verdict.kind == "truncated" and verdict.ok

    def test_length_finish_with_a_loop_is_a_loop_failure(self):
        verdict = classify_image_reply("Look at her now!!\nShe's awake!!\n" * 10, "length")
        assert verdict.kind == "loop" and not verdict.ok

    def test_unknown_finish_reason_is_treated_as_normal(self):
        assert kind("Halo dunia.", None) == "ok"
