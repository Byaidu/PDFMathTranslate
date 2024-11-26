import pytest
from pdf2zh.data_structures import NumberTree
from pdf2zh import settings


def test_number_tree_empty():
    tree = NumberTree({})
    assert tree.values == []


def test_number_tree_leaf():
    tree = NumberTree({"Nums": [1, "a", 2, "b", 3, "c"]})
    assert tree.values == [(1, "a"), (2, "b"), (3, "c")]


def test_number_tree_kids():
    child1 = {"Nums": [1, "a", 2, "b"]}
    child2 = {"Nums": [3, "c", 4, "d"]}
    tree = NumberTree({"Kids": [child1, child2]})
    assert tree.values == [(1, "a"), (2, "b"), (3, "c"), (4, "d")]


def test_number_tree_unordered():
    tree = NumberTree({"Nums": [3, "c", 1, "a", 2, "b"]})
    if settings.STRICT:
        with pytest.raises(Exception):
            tree.values
    else:
        assert tree.values == [(1, "a"), (2, "b"), (3, "c")]


def test_number_tree_limits():
    tree = NumberTree({"Nums": [1, "a"], "Limits": [1, 1]})
    assert tree.values == [(1, "a")]
    assert tree.limits == [1, 1]
