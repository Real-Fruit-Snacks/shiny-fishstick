from pathlib import Path

from delta_vision.screens.keywords_parser import parse_keywords_md


def write(tmp_path: Path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_parse_headers_and_keywords(tmp_path: Path):
    path = write(
        tmp_path,
        "kw.md",
        """
        # Fruits (red)
        apple
        banana  # yellow actually

        # Vegetables
        carrot
        # comment line ignored
        potato
        """,
    )

    out = parse_keywords_md(path)
    assert out["Fruits"][0] == "red"
    assert out["Fruits"][1] == ["apple", "banana"]
    assert out["Vegetables"][0] == ""
    assert out["Vegetables"][1] == ["carrot", "potato"]


def test_empty_category_preserved(tmp_path: Path):
    path = write(
        tmp_path,
        "kw2.md",
        """
        # EmptyCat

        # NonEmpty (blue)
        item1
        """,
    )
    out = parse_keywords_md(path)
    assert "EmptyCat" in out
    assert out["EmptyCat"] == ("", [])
    assert out["NonEmpty"] == ("blue", ["item1"])


def test_non_header_comment_ignored(tmp_path: Path):
    path = write(
        tmp_path,
        "kw3.md",
        """
        # Category
        one
        # not a header because it's not followed by name
        two
        """,
    )
    out = parse_keywords_md(path)
    assert out["Category"][1] == ["one", "two"]


def test_inline_comment_stripped(tmp_path: Path):
    path = write(
        tmp_path,
        "kw4.md",
        """
        # C
        foo  # bar baz
        bar#not stripped because no space before hash
        baz # trailing
        """,
    )
    out = parse_keywords_md(path)
    assert out["C"][1] == ["foo", "bar#not stripped because no space before hash", "baz"]
