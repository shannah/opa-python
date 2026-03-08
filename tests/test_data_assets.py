"""Tests for the DataIndex/DataEntry model."""

import json

from opa.data_assets import DataIndex, DataEntry


def test_data_entry():
    e = DataEntry("data/report.csv", description="Sales report", content_type="text/csv")
    d = e.to_dict()
    assert d["path"] == "data/report.csv"
    assert d["description"] == "Sales report"
    assert d["content_type"] == "text/csv"


def test_data_entry_minimal():
    e = DataEntry("data/file.txt")
    d = e.to_dict()
    assert d == {"path": "data/file.txt"}


def test_data_index():
    idx = DataIndex()
    idx.add("data/a.csv", description="File A")
    idx.add("data/b.json", content_type="application/json")
    lst = idx.to_list()
    assert len(lst) == 2


def test_data_index_json():
    idx = DataIndex()
    idx.add("data/x.txt")
    text = idx.to_json()
    parsed = json.loads(text)
    assert parsed == [{"path": "data/x.txt"}]
