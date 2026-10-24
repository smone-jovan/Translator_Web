import pytest

from routers.polish import clean_and_format_chapter_title


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Training Ground Run (2)", "007. Training Ground Run (2)"),
        ("Title [Part 1]", "007. Title [Part 1]"),
        ("Rencana (Final)", "007. Rencana (Final)"),
        ("Hope Center)", "007. Hope Center"),
        ("(Side Story)", "007. Side Story"),
        ("[Side Story]", "007. Side Story"),
        ('"Quoted"', "007. Quoted"),
        ("Arrest", "007. Arrest"),
    ],
)
def test_edge_wrappers_are_stripped_but_balanced_brackets_are_kept(raw, expected):
    assert clean_and_format_chapter_title(raw, order_num=7, total_chapters=100) == expected
