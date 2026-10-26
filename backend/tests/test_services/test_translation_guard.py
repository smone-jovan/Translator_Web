import pytest

from services.translation_guard import classify_image_reply, unwrap_labeled_quote


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

    @pytest.mark.parametrize("text", ["Ha ha ha ha ha ha!", "Ahahahahahahaha...", "Haa... haa... haa... haa... haa..."])
    def test_short_laughter_and_panting_are_not_a_loop(self, text):
        assert kind(text) == "ok"

    @pytest.mark.parametrize(
        "text",
        [
            "The character in the story is a knight. He draws his sword!",
            "The image of her face flashed in his mind. He could not forget it.",
            "The text on the sign said: Do not enter.",
        ],
    )
    def test_dialogue_that_merely_starts_like_a_description_is_ok(self, text):
        assert kind(text) == "ok"

    @pytest.mark.parametrize(
        "text",
        [
            "Karakter utamanya berlari ke arah gerbang sekolah.",
            "Gambarnya sungguh bagus, aku suka gaya komik ini!",
            "Di dalam kotak itu tertulis namamu.",
            "Manga ini aku beli kemarin, ceritanya seru.",
        ],
    )
    def test_indonesian_dialogue_that_starts_like_a_description_is_ok(self, text):
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

    @pytest.mark.parametrize(
        "text",
        [
            "The text in the image is written in bold, black calligraphy on a white background. It appears to be a sound effect; more context would be needed for an accurate interpretation.",
            "The image contains a stylized onomatopoeia character, likely from a manga, similar to \"whoa!\" in English.",
            "The character in the image is written in calligraphy. It appears to be a kanji symbol, but a clearer view would provide a more accurate translation.",
            "The character in the image is a stylized Japanese kana symbol, likely an onomatopoeia rather than a standard kanji.",
        ],
    )
    def test_english_description_of_a_sound_effect_is_a_description(self, text):
        assert kind(text) == "description"

    @pytest.mark.parametrize(
        "text",
        [
            'Karakter "Yo" dengan gaya kaligrafi hitam putih yang dinamis.',
            'Gambarnya adalah simbol "Yo" yang ditulis dengan gaya hitam tebal dan bersudut.',
            "Manga ini menampilkan dialog dalam bentuk teks Jepang dengan gaya komik hitam putih.",
            "Pada gambar ini terdapat teks dalam bahasa Jepang yang diterjemahkan sebagai berikut.",
            'Di dalam kotak dialog komik, teksnya berbunyi: "Saat kamu berdiri di panel itu".',
            "Dalam panel komik ini, ada dialog yang berbunyi: aku akan berdiri di sini.",
        ],
    )
    def test_indonesian_description_of_the_picture_is_a_description(self, text):
        assert kind(text) == "description"

    @pytest.mark.parametrize(
        "text",
        [
            "Gambar menunjukkan hitam-a...",
            "Gambar itu menampilkan seorang gadis berambut panjang.",
            "Gambar tersebut menggambarkan sebuah adegan pertarungan.",
            "Karakter (a) ditulis di dalam kurva hitam...",
            "Karakter A tertulis dengan huruf besar di tengah panel.",
        ],
    )
    def test_short_indonesian_descriptions_seen_from_the_second_model_are_descriptions(self, text):
        assert kind(text) == "description"

    def test_repeated_blocks_are_a_loop(self):
        block = '**Panel 4:**\n*Pink-haired girl:* "The neural link is important..."\n*Male:* "It\'s all here!!"\n---\n'
        assert kind("Intro line\n" + block * 6) == "loop"

    def test_repeated_long_phrase_in_one_line_is_a_loop(self):
        assert kind("She's awake! Her eyes are open! Her hands are moving! " * 8) == "loop"

    @pytest.mark.parametrize("unit", ["...Okay? ", "...What? ", "Stee... "])
    def test_short_phrase_repeated_on_one_line_is_a_loop(self, unit):
        assert kind("...Stop it! " + unit * 100) == "loop"

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


class TestUnwrapLabeledQuote:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('Teks di gambar ini adalah:  "Rupanya... aku datang ke toko!"  Terjemahan langsungnya begitu.', "Rupanya... aku datang ke toko!"),
            ('Teks di dalam gambar:   「数字が嫌な予感がする…」', "数字が嫌な予感がする…"),
            ('Manga: "Tangan dan kaki... Awalnya, panjangnya..."', "Tangan dan kaki... Awalnya, panjangnya..."),
            ('Teks dari gambar: "Langit tidak akan pernah kembali."', "Langit tidak akan pernah kembali."),
            ('Teks di gambar: “Ini adalah game!”', "Ini adalah game!"),
        ],
    )
    def test_label_and_quotes_around_the_translation_are_removed(self, raw, expected):
        assert unwrap_labeled_quote(raw) == expected

    @pytest.mark.parametrize(
        "text",
        ['"Halo," katanya sambil tersenyum.', 'Teks itu tertulis di dinding: "Awas".', "Aku akan pergi besok.", ""],
    )
    def test_ordinary_text_is_left_alone(self, text):
        assert unwrap_labeled_quote(text) == text


class TestMoreIndonesianMetaReplies:
    @pytest.mark.parametrize(
        "text",
        [
            'Karakter Jepang "あ" (a) dalam bentuk simbol.',
            'Berikutnya, saya akan menerjemahkan teks dari gambar Anda ke bahasa Indonesia. Namun, karena tidak ada gambar yang terlihat.',
            'Teks di gambar ini adalah gaya manga hitam putih dengan simbol kaligrafi.',
        ],
    )
    def test_is_not_a_translation(self, text):
        assert kind(text) in ("description", "refusal")


class TestUnwrapPreambleBeforeQuote:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('The text in the image is: "Take it, take it... don\'t go to the angel\'s mark..."', "Take it, take it... don't go to the angel's mark..."),
            ('The text in the image is written in Japanese calligraphy. Here\'s the translation:  "Early on, you should search for the answer."', "Early on, you should search for the answer."),
            ('This is a manga panel with Japanese text. The translation of the text would be: "Is this magic? Can I use it?" or something similar.', "Is this magic? Can I use it?"),
            ('Berikutnya adalah teks dari gambar:  "Kita harus mencapai tujuan itu..."', "Kita harus mencapai tujuan itu..."),
            ('Ini adalah teks dari sebuah manga, terjemahannya sebagai berikut:  "Jangan khawatir! Desainnya cocok banget!"   — Karakter pria', "Jangan khawatir! Desainnya cocok banget!"),
            ('Teks di gambar ini adalah tulisan Jepang yang diterjemahkan ke dalam bahasa Indonesia sebagai berikut:  "Semua rute harus dicek."', "Semua rute harus dicek."),
            ("Here's the translation:\n\nEarly on, you should search for the answer.", "Early on, you should search for the answer."),
            ("Berikut terjemahannya:\nKita pergi sekarang.", "Kita pergi sekarang."),
        ],
    )
    def test_preamble_around_the_translation_is_removed(self, raw, expected):
        assert unwrap_labeled_quote(raw) == expected

    @pytest.mark.parametrize(
        "text",
        ['He said: "Run!" and left.', 'Dia berkata: "Lari!" lalu pergi.', "Aku akan menerjemahkan ini nanti.", "What is this? Where are you going?"],
    )
    def test_ordinary_quotes_without_a_preamble_are_left_alone(self, text):
        assert unwrap_labeled_quote(text) == text


class TestPreambleWithoutTheTranslation:
    @pytest.mark.parametrize(
        "text",
        [
            "Teks di gambar ini adalah judul anime dengan gaya Jepang.",
            "Gambar ini menunjukkan teks dalam bahasa Jepang yang sulit dibaca.",
            "The image shows a close-up of a face with a surprised expression.",
            "This is a manga panel with Japanese text.",
            "Berikut adalah deskripsi dari gambar tersebut.",
        ],
    )
    def test_is_not_a_translation(self, text):
        assert kind(text) == "description"


class TestMoreRealWorldWrappers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('Kata-kata yang tertulis di gambar: "Teman-teman, apa kalian tahu?" dengan tulisan tangan Jepang.', "Teman-teman, apa kalian tahu?"),
            ('Teks di dalam kotak dialognya adalah: "Ini belum... ini belum selesai..."', "Ini belum... ini belum selesai..."),
        ],
    )
    def test_more_lead_ins_are_unwrapped(self, raw, expected):
        assert unwrap_labeled_quote(raw) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Gambarnya adalah gambar karakter komik putih dengan ekspresi di wajahnya.",
            "Gambarnya adalah bagian dari manga dengan tulisan dan simbol hati.",
            "Karakter komik dengan bentuk lingkaran putih, di dalamnya terdapat simbol.",
            "**Judul Asli:** **Contoh** **Terjemahan Indonesia:** Contoh",
        ],
    )
    def test_commentary_without_a_translation_is_a_description(self, text):
        assert kind(text) == "description"

    @pytest.mark.parametrize(
        "text",
        ["Gambarnya bagus sekali, kamu yang menggambar?", "Karakter utamanya kuat sekali!", "Judul bukunya apa?"],
    )
    def test_dialogue_that_starts_similarly_is_ok(self, text):
        assert kind(text) == "ok"
