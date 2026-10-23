import pytest
from network import build_network, highlight_differences


def test_relationships_and_isolated_are_separate():
    reports = [{"text": x} for x in ("a", "b", "c", "d")]
    matrix = [[1, .8, 0, 0], [.8, 1, .75, 0], [0, .75, 1, .1], [0, 0, .1, 1]]
    result = build_network(reports, matrix, .7)
    assert len(result['edges']) == 2
    assert result['components'] == [[0, 1, 2], [3]]
    assert len(result['nodes']) == 4
    assert result['nodes'][0]['degree'] == 1


def test_edges_are_undirected_and_not_arrows():
    reports = [{"text": "a"}, {"text": "b"}]
    graph = build_network(reports, [[1, .8], [.8, 1]], .75)
    assert graph['edges'] == [{'source': 0, 'target': 1, 'weight': .8}]


def test_bad_matrix_rejected():
    with pytest.raises(ValueError):
        build_network([{"text": "a"}], [[1, 2]], .6)


def test_diff_marks_changes_and_escapes_html():
    left, right = highlight_differences('Makerere <script> may close', 'Makerere <script> HAS closed')
    assert '<script>' not in left + right
    assert '&lt;script&gt;' in left + right
    assert 'rp-diff-add' in right
    assert 'rp-diff-remove' in left


def test_empty_library_safe():
    assert build_network([], [], .6) == {'nodes': [], 'edges': [], 'components': []}
