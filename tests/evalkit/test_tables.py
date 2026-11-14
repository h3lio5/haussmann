from haussmann.evalkit.tables import Table, read_tables

TEXT = """# Log

Some prose.

| id | change |
|---|---|
| E1 | first |
| E2 | second, with `code` |

## By type

| system | unit |
|:--|--:|
| engine | 9/9 |
not a row
"""


def test_each_table_is_read_with_the_heading_above_it() -> None:
    assert read_tables(TEXT) == [
        Table("Log", ("id", "change"), (("E1", "first"), ("E2", "second, with `code`"))),
        Table("By type", ("system", "unit"), (("engine", "9/9"),)),
    ]


def test_a_line_of_bars_without_a_rule_is_not_a_table() -> None:
    assert read_tables("| a | b |\n| c | d |\n") == []


def test_a_row_with_another_number_of_cells_ends_the_table() -> None:
    tables = read_tables("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 |\n")
    assert tables == [Table("", ("a", "b"), (("1", "2"),))]


def test_text_without_a_table_gives_nothing() -> None:
    assert read_tables("# Title\n\nwords\n") == []
