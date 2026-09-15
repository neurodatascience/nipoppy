"""Tests for the tabular module."""

from contextlib import nullcontext
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from nipoppy.exceptions import TabularError
from nipoppy.tabular.base import BaseTabular, BaseTabularModel
from tests.conftest import DPATH_TEST_DATA


class Tabular(BaseTabular):
    model = BaseTabularModel


class TabularWithModel(BaseTabular):
    class _Model(BaseTabularModel):
        a: str
        b: int | None = 0
        c: list = []
        d: list | str = []

    model: BaseTabularModel = _Model
    index_cols = ["b"]


class TabularWithModelNoList(BaseTabular):
    class _Model(BaseTabularModel):
        a: str
        b: int = 0
        c: str = "s"

    model: BaseTabularModel = _Model
    index_cols = ["b"]


def test_init_empty_has_columns():
    tabular = TabularWithModel()
    assert set(tabular.columns) == set(TabularWithModel.model.model_fields.keys())


def test_init_dtypes():
    tabular1 = TabularWithModel()
    tabular2 = TabularWithModel([{"a": "A", "b": 1, "c": [], "d": None}])
    assert tabular1.dtypes.equals(tabular2.dtypes)


def test_sort_index_does_not_change_columns():
    tabular = TabularWithModel()
    tabular = tabular.set_index(tabular.index_cols)
    tabular = tabular.sort_index()

    # make sure the index columns have not been re-added to the columns
    assert len(set(tabular.index_cols) & set(tabular.columns)) == 0


@pytest.mark.parametrize(
    "fpath",
    [
        DPATH_TEST_DATA / "manifest1.tsv",
        DPATH_TEST_DATA / "manifest2.tsv",
        DPATH_TEST_DATA / "manifest_invalid1.tsv",
        DPATH_TEST_DATA / "manifest_invalid2.tsv",
    ],
)
@pytest.mark.parametrize("tabular_class", [Tabular, TabularWithModel])
def test_load(fpath, tabular_class: BaseTabular):
    assert isinstance(tabular_class.load(fpath, validate=False), tabular_class)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dtype": str},
        {"dtype": int},
        {"sep": ","},
        {"delimiter": "\t"},
        {"delim_whitespace": True},
    ],
)
def test_load_error(kwargs):
    fpath_tabular = DPATH_TEST_DATA / "manifest1.tsv"
    with pytest.raises(TabularError, match="This function does not accept"):
        Tabular.load(fpath_tabular, **kwargs)


def test_load_error_csv(tmp_path: Path):
    fpath_tsv = DPATH_TEST_DATA / "manifest1.tsv"
    fpath_csv = tmp_path / fpath_tsv.with_suffix(".csv").name
    pd.read_csv(fpath_tsv, sep="\t").to_csv(fpath_csv, index=False)
    with pytest.raises(
        TabularError, match="It looks like the file at .* might be a CSV"
    ):
        Tabular.load(fpath_csv)


@pytest.mark.parametrize(
    "data,is_valid",
    [
        ([{"a": "A", "b": 1}], True),
        ([{"a": "AA", "b": pd.NA}], True),
        ([{"a": "AAA", "b": None}], True),
        ([{"a": "A", "b": "0"}], True),
        ([{"a": 1, "b": 1}], False),
        ([{"a": "A", "b": "b"}], False),
    ],
)
def test_validate(data, is_valid):
    tabular = TabularWithModel(data)
    with (
        pytest.raises(
            TabularError, match="Error when validating the tabular with model file"
        )
        if not is_valid
        else nullcontext()
    ):
        assert isinstance(tabular.validate(), TabularWithModel)


def test_validate_all_required_fields_present():
    tabular = TabularWithModel([{"b": 0}])
    with pytest.raises(TabularError):
        assert isinstance(tabular.validate(), TabularWithModel)


@pytest.mark.parametrize(
    "data",
    [
        [{"a": "A", "b": 1}, {"a": "A", "b": 1}],
        [{"a": "A", "b": 1}, {"a": "AA", "b": 1}],
        [{"a": "A", "b": 1}, {"a": "AA", "b": 1}, {"a": "AAA", "b": 2}],
    ],
)
def test_validate_duplicate_records(data):
    tabular = TabularWithModel(data)
    with pytest.raises(TabularError, match="Duplicate records"):
        assert isinstance(tabular.validate(), TabularWithModel)


@pytest.mark.parametrize(
    "data1,data2,expected_count",
    [
        (
            {"a": ["A", "B", "C", "D"], "b": [1, 2, 3, 4]},
            {"a": ["A", "B", "C", "D"], "b": [1, 2, 3, 4]},
            0,
        ),
        (
            {"a": ["A", "B", "C", "D"], "b": [1, 2, 3, 4]},
            {"a": ["A", "B", "C"], "b": [1, 2, 3]},
            1,
        ),
        ({"a": ["A", "B", "C", "D"], "b": [1, 2, 3, 4]}, {"a": [], "b": []}, 4),
        ({"a": [], "b": []}, {"a": ["A", "B"], "b": [1, 2]}, 0),
    ],
)
def test_get_diff(data1, data2, expected_count):
    manifest1 = TabularWithModel(data1)
    manifest2 = TabularWithModel(data2)
    diff = manifest1.get_diff(manifest2)
    assert isinstance(diff, TabularWithModel)
    assert len(diff) == expected_count


@pytest.mark.parametrize(
    "cols,expected_count", [(None, 0), (["a"], 2), ("a", 2), (["a", "b"], 4)]
)
def test_get_diff_cols(cols, expected_count):
    data1 = {"a": ["A", "B", "C", "A", "B", "C"], "b": [1, 1, 1, 2, 2, 2]}
    data2 = {"a": ["A", "A", "C"], "b": [1, 3, 2]}
    manifest1 = TabularWithModel(data1)
    manifest2 = TabularWithModel(data2)
    diff = manifest1.get_diff(manifest2, cols=cols)
    assert isinstance(diff, TabularWithModel)
    assert len(diff) == expected_count


def test_get_diff_invalid_cols():
    data1 = {"a": ["A"], "b": [1]}
    data2 = {"a": ["A"]}
    manifest1 = TabularWithModel(data1)
    manifest2 = TabularWithModel(data2)
    with pytest.raises(TabularError, match="The columns .* are not present"):
        manifest1.get_diff(manifest2, cols="b")


@pytest.mark.parametrize(
    "original,index_cols,to_add,expected",
    [
        [
            [{"a": "A", "b": 1}],
            ["b"],
            [],
            [{"a": "A", "b": 1}],
        ],
        [
            [{"a": "A", "b": 1}],
            ["b"],
            [{"a": "A", "b": 1}],
            [{"a": "A", "b": 1}],
        ],
        [
            [{"a": "A", "b": 1}],
            ["b"],
            [{"a": "A", "b": 0}],
            [{"a": "A", "b": 1}, {"a": "A", "b": 0}],
        ],
        [
            [{"a": "A", "b": 1, "c": "4"}],
            ["a", "b"],
            [{"a": "A", "b": 1, "c": "4"}],
            [{"a": "A", "b": 1, "c": "4"}],
        ],
        [
            [{"a": "A", "b": 1, "c": "3"}],
            ["a", "b"],
            [{"a": "A", "b": 0, "c": "4"}],
            [{"a": "A", "b": 1, "c": "3"}, {"a": "A", "b": 0, "c": "4"}],
        ],
    ],
)
def test_add_or_update_records(original, index_cols, to_add, expected):
    tabular = TabularWithModelNoList(original)
    tabular.index_cols = index_cols
    tabular = tabular.add_or_update_records(to_add)
    assert tabular.to_dict(orient="records") == expected


def test_add_or_update_records_index_reset():
    data = [{"a": "A", "b": 1, "c": "s"}]
    tabular = TabularWithModelNoList(data)

    # expect error since added data is invalid
    with pytest.raises(ValidationError):
        tabular.add_or_update_records([{"a": "A", "b": "invalid", "c": "s"}])

    # check that index has been reset
    assert set(tabular.columns) == {"a", "b", "c"}
    assert isinstance(tabular.index, pd.RangeIndex)


@pytest.mark.parametrize(
    "data1,data2",
    [
        ([], [{"a": "A", "b": "1"}]),
        ([{"a": "A", "b": "1"}], [{"a": "A", "b": "2"}]),
        ([{"a": "A", "b": "1"}, {"a": "A", "b": "2"}], []),
        ([{"a": "A", "b": 1}, {"a": "A", "b": 2}], [{"a": "A", "b": "3"}]),
    ],
)
def test_concatenate(data1: list[dict], data2: list[dict]):
    tabular1 = TabularWithModel(data1)
    assert len(tabular1) == len(data1)
    assert isinstance(tabular1, TabularWithModel)
    tabular2 = TabularWithModel(data2)
    assert len(tabular2) == len(data2)
    assert isinstance(tabular2, TabularWithModel)
    tabular_concatenated = tabular1.concatenate(tabular2)
    assert len(tabular_concatenated) == len(data1) + len(data2)
    assert isinstance(tabular_concatenated, TabularWithModel)


@pytest.mark.parametrize(
    "data1,data2",
    [
        ([{"a": "A", "b": "1"}], [{"a": "A", "b": "1"}]),
        ([{"a": "A", "b": "1"}, {"a": "A", "b": "2"}], [{"a": "A", "b": "1"}]),
    ],
)
def test_concatenate_error(data1: list[dict], data2: list[dict]):
    tabular1 = TabularWithModel(data1)
    tabular2 = TabularWithModel(data2)
    with pytest.raises(TabularError):
        tabular1.concatenate(tabular2, validate=True)


@pytest.mark.parametrize("dname_backups", [None, ".tests"])
@pytest.mark.parametrize(
    "fname,dname_backups_processed",
    [("test.tsv", ".tests"), ("test2.tsv", ".test2s")],
)
def test_save_with_backup(
    fname: str,
    dname_backups: str | None,
    dname_backups_processed: str,
    tmp_path: Path,
):
    fpath_symlink = tmp_path / fname
    tabular = TabularWithModel([{"a": "A", "b": 1}])
    fpath_backup = tabular.save_with_backup(fpath_symlink, dname_backups)

    if dname_backups is None:
        dname_backups = dname_backups_processed

    assert fpath_symlink.exists()
    assert fpath_symlink.is_symlink()
    assert fpath_backup.exists()
    assert fpath_backup.parent == fpath_symlink.parent / dname_backups
    assert isinstance(TabularWithModel.load(fpath_symlink), TabularWithModel)


@pytest.mark.parametrize(
    "data1,data2",
    [
        ([{"a": "A", "b": 1, "c": "s"}], [{"a": "A", "b": 1, "c": "s"}]),
        (
            [{"a": "a", "b": 1, "c": "s"}, {"a": "a", "b": 2, "c": "s"}],
            [{"a": "a", "b": 2, "c": "s"}, {"a": "a", "b": 1, "c": "s"}],
        ),
    ],
)
def test_save_with_backup_no_change(data1, data2, tmp_path: Path):
    fpath_symlink = tmp_path / "test.tsv"
    tabular1 = TabularWithModelNoList(data1)
    fpath_backup1 = tabular1.save_with_backup(fpath_symlink)
    assert fpath_backup1 is not None
    tabular2 = TabularWithModelNoList(data2)
    assert tabular2.save_with_backup(fpath_symlink) is None
    assert len(list(fpath_backup1.parent.iterdir())) == 1


@pytest.mark.parametrize("bad_data", [{}, [{"b": 1}]])
def test_save_with_backup_invalid_existing(bad_data, tmp_path: Path):
    fpath_symlink = tmp_path / "test.tsv"

    # not a valid TabularWithModel
    pd.DataFrame(bad_data).to_csv(fpath_symlink, index=False, sep="\t")

    tabular = TabularWithModel([{"a": "A", "b": 1}])
    assert tabular.save_with_backup(fpath_symlink) is not None


@pytest.mark.parametrize(
    "data1,data2,equal",
    [
        ([{"a": "A", "b": 1}], [{"a": "A", "b": 1}], True),
        ([{"a": "A", "b": 1}], [{"a": "A", "b": 2}], False),
        ([{"a": "A", "b": 1, "c": [1]}], [{"a": "A", "b": 1, "c": [1]}], True),
        ([{"a": "A", "c": [1]}], [{"a": "A", "c": [1, 2]}], False),
        ([{"a": "A", "b": 1}], [{"b": 1, "a": "A"}], True),
        ([{"a": "A"}, {"a": "a"}], [{"a": "a"}, {"a": "A"}], False),
    ],
)
def test_equals(data1, data2, equal):
    tabular1 = TabularWithModel(data1)
    tabular2 = TabularWithModel(data2)
    if equal:
        assert tabular1.equals(tabular2)
    else:
        assert not tabular1.equals(tabular2)


def test_equals_validated():
    data1 = [{"a": "A", "b": 1, "c": []}]
    data2 = [{"a": "A", "b": 1}]
    tabular1 = TabularWithModel(data1).validate()
    tabular2 = TabularWithModel(data2).validate()
    assert tabular1.equals(tabular2)


@pytest.mark.parametrize(
    "data_before,data_after,ascending",
    [
        (
            [{"a": "A", "b": 2}, {"a": "A", "b": 1}],
            [{"a": "A", "b": 1}, {"a": "A", "b": 2}],
            True,
        ),
        (
            [{"a": "A", "b": 1}, {"a": "A", "b": 2}],
            [{"a": "A", "b": 2}, {"a": "A", "b": 1}],
            False,
        ),
    ],
)
@pytest.mark.parametrize("inplace", [False, True])
def test_sort_values(data_before, data_after, ascending, inplace):
    tabular = TabularWithModel(data_before)
    tabular_sorted = tabular.sort_values(ascending=ascending, inplace=inplace)
    if inplace:
        assert tabular_sorted is None
        tabular_sorted = tabular
    assert isinstance(tabular_sorted, TabularWithModel)
    pd.testing.assert_frame_equal(tabular_sorted, TabularWithModel(data_after))


def test_constructor_overrides():
    record = {"a": "a", "b": None}
    tabular = TabularWithModel([record])

    assert isinstance(tabular[list(record.keys())[0]].to_frame(), TabularWithModel)
    assert isinstance(tabular.fillna("x"), TabularWithModel)
