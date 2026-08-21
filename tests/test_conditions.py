# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Any

import pytest

from costformation import conditions
from costformation.core_dimensions import Account, Service
from costformation.transforms import Lower, Upper

SERVICE_DATA = {'Service': 'AmazonEC2'}


class _Always(conditions.Condition):
    def __init__(self, result: bool):
        self.result = result

    def to_dict(self) -> dict[str, Any]:
        return {'Always': self.result}

    def evaluate(self, data: dict[str, Any], source: object = None) -> bool:
        return self.result


@pytest.mark.unit
def test_condition_and_operator_should_create_and():
    combined = _Always(True) & _Always(False)
    assert isinstance(combined, conditions.And)
    assert len(combined.conditions) == 2


@pytest.mark.unit
def test_condition_or_operator_should_create_or():
    combined = _Always(True) | _Always(False)
    assert isinstance(combined, conditions.Or)
    assert len(combined.conditions) == 2


@pytest.mark.unit
def test_condition_invert_operator_should_create_not():
    negated = ~_Always(True)
    assert isinstance(negated, conditions.Not)
    assert negated.condition.result is True


@pytest.mark.unit
@pytest.mark.parametrize(
    'cls',
    [
        pytest.param(conditions.And, id='and'),
        pytest.param(conditions.Or, id='or'),
    ],
)
def test_logical_combinator_should_raise_when_empty(cls):
    with pytest.raises(ValueError, match='at least 1 condition'):
        cls()


@pytest.mark.unit
@pytest.mark.parametrize(
    'cls, key',
    [
        pytest.param(conditions.And, 'And', id='and'),
        pytest.param(conditions.Or, 'Or', id='or'),
    ],
)
def test_logical_combinator_to_dict_should_serialize_conditions(cls, key):
    result = cls(_Always(True), _Always(False)).to_dict()
    assert result == {key: [{'Always': True}, {'Always': False}]}


@pytest.mark.unit
@pytest.mark.parametrize(
    'cls, key',
    [
        pytest.param(conditions.And, 'And', id='and'),
        pytest.param(conditions.Or, 'Or', id='or'),
    ],
)
def test_logical_combinator_should_flatten_same_type_nesting(cls, key):
    a, b, c = _Always(True), _Always(False), _Always(True)
    nested_left = cls(cls(a, b), c)
    nested_right = cls(a, cls(b, c))
    deeply_nested = cls(cls(a, cls(b, c)))
    explicit_flat = cls(a, b, c)

    for combo in (nested_left, nested_right, deeply_nested, explicit_flat):
        assert combo.conditions == [a, b, c], f'flattening failed for {combo!r}'
        assert combo.to_dict() == {key: [{'Always': True}, {'Always': False}, {'Always': True}]}


@pytest.mark.unit
@pytest.mark.parametrize(
    'outer, inner',
    [
        pytest.param(conditions.And, conditions.Or, id='and-wrapping-or'),
        pytest.param(conditions.Or, conditions.And, id='or-wrapping-and'),
    ],
)
def test_logical_combinator_should_not_flatten_across_different_types(outer, inner):
    a, b, c = _Always(True), _Always(False), _Always(True)
    combo = outer(a, inner(b, c))
    # inner operator of different type must remain nested (2 children, not 3)
    assert len(combo.conditions) == 2
    assert combo.conditions[0] is a
    assert isinstance(combo.conditions[1], inner)
    assert combo.conditions[1].conditions == [b, c]


@pytest.mark.unit
def test_chained_operators_should_flatten_via_init():
    a, b, c, d = _Always(True), _Always(False), _Always(True), _Always(False)
    # & and | are left-associative in Python, so these naively produce nested
    # binary trees. The flattening in __init__ should collapse them.
    assert (a & b & c & d).conditions == [a, b, c, d]
    assert (a | b | c | d).conditions == [a, b, c, d]


@pytest.mark.unit
@pytest.mark.parametrize(
    'results, expected',
    [
        pytest.param([True], True, id='single-true'),
        pytest.param([False], False, id='single-false'),
        pytest.param([True, True, True], True, id='all-true'),
        pytest.param([True, False, True], False, id='one-false'),
        pytest.param([False, False], False, id='all-false'),
    ],
)
def test_and_evaluate_should_require_all_conditions_true(results, expected):
    cond = conditions.And(*(_Always(r) for r in results))
    assert cond.evaluate({}) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'results, expected',
    [
        pytest.param([True], True, id='single-true'),
        pytest.param([False], False, id='single-false'),
        pytest.param([False, False, True], True, id='one-true'),
        pytest.param([False, False, False], False, id='all-false'),
    ],
)
def test_or_evaluate_should_require_any_condition_true(results, expected):
    cond = conditions.Or(*(_Always(r) for r in results))
    assert cond.evaluate({}) is expected


@pytest.mark.unit
def test_not_to_dict_should_wrap_inner_in_list():
    result = conditions.Not(_Always(True)).to_dict()
    assert result == {'Not': [{'Always': True}]}


@pytest.mark.unit
@pytest.mark.parametrize(
    'inner, expected',
    [
        pytest.param(True, False, id='inverts-true'),
        pytest.param(False, True, id='inverts-false'),
    ],
)
def test_not_evaluate_should_invert_inner(inner, expected):
    assert conditions.Not(_Always(inner)).evaluate({}) is expected


# ---------------------------------------------------------------------------
# _SourcedCondition base-class behavior (exercised through Equals; Matches and
# HasValue override __init__/evaluate and get their own dedicated tests).
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    'factory',
    [
        pytest.param(lambda **kw: conditions.Equals('v', **kw), id='equals'),
        pytest.param(lambda **kw: conditions.Matches(r'foo', **kw), id='matches'),
        pytest.param(lambda **kw: conditions.HasValue(**kw), id='has-value'),
    ],
)
def test_sourced_condition_should_reject_both_source_and_sources(factory):
    with pytest.raises(ValueError, match='Cannot specify both'):
        factory(source=Service(), sources=[Account()])


@pytest.mark.unit
def test_value_condition_to_dict_should_omit_source_when_unset():
    assert conditions.Equals('AmazonEC2').to_dict() == {'Equals': 'AmazonEC2'}


@pytest.mark.unit
@pytest.mark.parametrize(
    'kwargs, expected_extras',
    [
        pytest.param({'source': Service()}, {'Source': 'Service'}, id='single-source'),
        pytest.param({'sources': [Service()]}, {'Sources': 'Service'}, id='single-element-sources-collapsed'),
        pytest.param({'sources': [Service(), Account()]}, {'Sources': ['Service', 'Account']}, id='multiple-sources'),
    ],
)
def test_value_condition_to_dict_should_serialize_source_kwargs(kwargs, expected_extras):
    assert conditions.Equals('AmazonEC2', **kwargs).to_dict() == {'Equals': 'AmazonEC2', **expected_extras}


@pytest.mark.unit
def test_value_condition_to_dict_should_include_transforms():
    result = conditions.Equals('amazonec2', source=Service(), transforms=[Lower(), Upper()]).to_dict()
    assert result['Transforms'] == [{'Type': 'Lower'}, {'Type': 'Upper'}]


@pytest.mark.unit
def test_value_condition_evaluate_should_raise_without_source():
    with pytest.raises(ValueError, match='requires a source'):
        conditions.Equals('value').evaluate(SERVICE_DATA)


@pytest.mark.unit
def test_value_condition_evaluate_should_use_runtime_source_when_unset():
    assert conditions.Equals('AmazonEC2').evaluate(SERVICE_DATA, source=Service()) is True


@pytest.mark.unit
def test_value_condition_evaluate_should_return_false_when_dimension_missing():
    assert conditions.Equals('AmazonEC2', source=Service()).evaluate({}) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    'condition_cls, expected_key',
    [
        pytest.param(conditions.Contains, 'Contains', id='contains'),
        pytest.param(conditions.BeginsWith, 'BeginsWith', id='begins-with'),
        pytest.param(conditions.EndsWith, 'EndsWith', id='ends-with'),
        pytest.param(conditions.Before, 'Before', id='before'),
        pytest.param(conditions.BeforeOrEquals, 'BeforeOrEquals', id='before-or-equals'),
        pytest.param(conditions.After, 'After', id='after'),
        pytest.param(conditions.AfterOrEquals, 'AfterOrEquals', id='after-or-equals'),
    ],
)
def test_sourced_condition_should_emit_its_yaml_key(condition_cls, expected_key):
    assert condition_cls('N', source=Service()).to_dict() == {expected_key: 'N', 'Source': 'Service'}


# ---------------------------------------------------------------------------
# Per-class _matches behavior (Equals/Matches/HasValue to_dict has dedicated
# coverage above or below).
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    'value, data, expected',
    [
        pytest.param('AmazonEC2', SERVICE_DATA, True, id='scalar-match'),
        pytest.param('AmazonS3', SERVICE_DATA, False, id='scalar-miss'),
        pytest.param(['AmazonEC2', 'AmazonS3'], SERVICE_DATA, True, id='list-match'),
        pytest.param(['AmazonS3', 'AmazonRDS'], SERVICE_DATA, False, id='list-miss'),
    ],
)
def test_equals_should_match_scalar_or_list(value, data, expected):
    assert conditions.Equals(value, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'value, data, expected',
    [
        pytest.param('EC2', SERVICE_DATA, True, id='scalar-substring-match'),
        pytest.param('S3', SERVICE_DATA, False, id='scalar-substring-miss'),
        pytest.param(['S3', 'EC2'], SERVICE_DATA, True, id='list-any-match'),
        pytest.param(['S3', 'RDS'], SERVICE_DATA, False, id='list-all-miss'),
    ],
)
def test_contains_should_match_substring(value, data, expected):
    assert conditions.Contains(value, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'factory',
    [
        pytest.param(lambda **kw: conditions.Equals('AmazonEC2', **kw), id='equals'),
        pytest.param(lambda **kw: conditions.Contains('EC2', **kw), id='contains'),
        pytest.param(lambda **kw: conditions.BeginsWith('Amazon', **kw), id='begins-with'),
        pytest.param(lambda **kw: conditions.Matches(r'Amazon.*', **kw), id='matches'),
    ],
)
@pytest.mark.parametrize(
    'data, expected',
    [
        pytest.param({'Service': 'AmazonEC2'}, True, id='first-source-matches'),
        pytest.param({'Account': 'AmazonEC2'}, True, id='second-source-matches'),
        pytest.param({'Service': 'other', 'Account': 'AmazonEC2'}, True, id='second-matches-when-first-does-not'),
        pytest.param({'Service': 'other'}, False, id='only-populated-source-does-not-match'),
        pytest.param({}, False, id='no-sources-populated'),
    ],
)
def test_sourced_condition_with_sources_should_match_if_any_source_matches(factory, data, expected):
    assert factory(sources=[Service(), Account()]).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'value, data, expected',
    [
        pytest.param('Amazon', SERVICE_DATA, True, id='scalar-prefix-match'),
        pytest.param('Google', SERVICE_DATA, False, id='scalar-prefix-miss'),
        pytest.param(['Google', 'Amazon'], SERVICE_DATA, True, id='list-any-match'),
        pytest.param(['Google', 'Azure'], SERVICE_DATA, False, id='list-all-miss'),
    ],
)
def test_begins_with_should_match_prefix(value, data, expected):
    assert conditions.BeginsWith(value, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'value, data, expected',
    [
        pytest.param('EC2', SERVICE_DATA, True, id='scalar-suffix-match'),
        pytest.param('S3', SERVICE_DATA, False, id='scalar-suffix-miss'),
        pytest.param(['S3', 'EC2'], SERVICE_DATA, True, id='list-any-match'),
        pytest.param(['S3', 'RDS'], SERVICE_DATA, False, id='list-all-miss'),
    ],
)
def test_ends_with_should_match_suffix(value, data, expected):
    assert conditions.EndsWith(value, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'condition_cls, value, dim_value, expected',
    [
        pytest.param(conditions.Before, 'N', 'Amazon', True, id='before-true'),
        pytest.param(conditions.Before, 'A', 'Amazon', False, id='before-false-greater'),
        pytest.param(conditions.Before, 'Amazon', 'Amazon', False, id='before-false-equal'),
        pytest.param(conditions.BeforeOrEquals, 'Amazon', 'Amazon', True, id='before-or-equals-equal'),
        pytest.param(conditions.BeforeOrEquals, 'N', 'Amazon', True, id='before-or-equals-less'),
        pytest.param(conditions.BeforeOrEquals, 'A', 'Amazon', False, id='before-or-equals-greater'),
        pytest.param(conditions.After, 'A', 'Amazon', True, id='after-true'),
        pytest.param(conditions.After, 'N', 'Amazon', False, id='after-false-less'),
        pytest.param(conditions.After, 'Amazon', 'Amazon', False, id='after-false-equal'),
        pytest.param(conditions.AfterOrEquals, 'Amazon', 'Amazon', True, id='after-or-equals-equal'),
        pytest.param(conditions.AfterOrEquals, 'A', 'Amazon', True, id='after-or-equals-greater'),
        pytest.param(conditions.AfterOrEquals, 'N', 'Amazon', False, id='after-or-equals-less'),
    ],
)
def test_comparison_conditions_should_order_lexicographically(condition_cls, value, dim_value, expected):
    cond = condition_cls(value, source=Service())
    assert cond.evaluate({'Service': dim_value}) is expected


# ---------------------------------------------------------------------------
# Matches (overrides __init__ to compile the regex)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    'pattern, data, expected',
    [
        # Full-string match required (Snowflake auto-anchors)
        pytest.param(r'AmazonEC2', SERVICE_DATA, True, id='bare-exact-match'),
        pytest.param(r'Amazon', SERVICE_DATA, False, id='bare-prefix-no-fullmatch'),
        pytest.param(r'Amazon.*', SERVICE_DATA, True, id='prefix-wildcard'),
        pytest.param(r'.*EC2', SERVICE_DATA, True, id='suffix-wildcard'),
        pytest.param(r'.*\d+', SERVICE_DATA, True, id='digit-anywhere'),
        pytest.param(r'^AmazonEC2$', SERVICE_DATA, True, id='explicit-anchors'),
        pytest.param(r'Google.*', SERVICE_DATA, False, id='prefix-miss'),
        # Alternation: each branch must fully match
        pytest.param(r'AmazonEC2|AmazonS3', SERVICE_DATA, True, id='alternation-first-branch'),
        pytest.param(r'AmazonEC2|S3', {'Service': 'AmazonEC2XX'}, False, id='alternation-no-partial'),
    ],
)
def test_matches_should_use_fullmatch_semantics(pattern, data, expected):
    assert conditions.Matches(pattern, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'pattern, input_pattern_translates_to',
    [
        pytest.param(r'[[:alpha:]]+', r'[A-Za-z]+', id='alpha'),
        pytest.param(r'[[:digit:]]+', r'[0-9]+', id='digit'),
        pytest.param(r'[[:alnum:]]+', r'[A-Za-z0-9]+', id='alnum'),
        pytest.param(r'[[:alpha:]_-]+', r'[A-Za-z_-]+', id='alpha-inside-larger-class'),
        pytest.param(r'[[:alpha:][:digit:]]+', r'[A-Za-z0-9]+', id='two-posix-inside-one-class'),
    ],
)
def test_matches_should_translate_posix_bracket_classes(pattern, input_pattern_translates_to):
    # Verify by comparing the evaluation outcome against the expected raw-Python pattern
    sample_inputs = ['abc', 'ABC123', 'abc_-xyz', 'abc-def', '']
    for value in sample_inputs:
        via_matches = conditions.Matches(pattern, source=Service()).evaluate({'Service': value})
        via_python = re.fullmatch(input_pattern_translates_to, value, re.ASCII) is not None
        assert via_matches is via_python, f'diverged on value {value!r}'


@pytest.mark.unit
def test_matches_should_raise_on_unknown_posix_class():
    with pytest.raises(ValueError, match="Unknown POSIX character class '\\[:bogus:\\]'"):
        conditions.Matches(r'[[:bogus:]]+', source=Service())


@pytest.mark.unit
def test_matches_shorthand_d_should_be_ascii_only():
    ascii_match = conditions.Matches(r'\d', source=Service()).evaluate({'Service': '5'})
    fullwidth_match = conditions.Matches(r'\d', source=Service()).evaluate({'Service': '\uff15'})
    assert ascii_match is True
    assert fullwidth_match is False


@pytest.mark.unit
@pytest.mark.parametrize(
    'pattern, construct_label',
    [
        pytest.param(r'a(?=b)bc', 'lookahead', id='lookahead-pos'),
        pytest.param(r'a(?!b)bc', 'negative lookahead', id='lookahead-neg'),
        pytest.param(r'(?<=a)bc', 'lookbehind', id='lookbehind-pos'),
        pytest.param(r'(?<!a)bc', 'negative lookbehind', id='lookbehind-neg'),
        pytest.param(r'(?P<x>abc)', 'named group', id='named-group'),
        pytest.param(r'(?P=x)', 'named backreference', id='named-backref'),
        pytest.param(r'(?#a comment)abc', 'inline comment', id='inline-comment'),
        pytest.param(r'(?i)abc', 'inline flags', id='inline-flag-i'),
        pytest.param(r'(?s:abc)', 'inline flags', id='inline-flag-scoped'),
        pytest.param(r'(ab)\1', 'backreference', id='backref-1'),
        pytest.param(r'a*?b', 'non-greedy', id='non-greedy-star'),
        pytest.param(r'a+?b', 'non-greedy', id='non-greedy-plus'),
        pytest.param(r'a??b', 'non-greedy', id='non-greedy-q'),
    ],
)
def test_matches_should_reject_unsupported_python_constructs(pattern, construct_label):
    with pytest.raises(ValueError, match=construct_label):
        conditions.Matches(pattern, source=Service())


@pytest.mark.unit
def test_matches_should_raise_at_construction_for_invalid_regex():
    with pytest.raises(Exception, match='unbalanced parenthesis|missing'):
        conditions.Matches(r'(unclosed', source=Service())


@pytest.mark.unit
def test_matches_to_dict_should_serialize_pattern():
    assert conditions.Matches(r'^Amazon.*', source=Service()).to_dict() == {
        'Matches': r'^Amazon.*',
        'Source': 'Service',
    }


@pytest.mark.unit
def test_matches_pattern_property_should_expose_value():
    assert conditions.Matches(r'^Amazon', source=Service()).pattern == r'^Amazon'


# ---------------------------------------------------------------------------
# HasValue (overrides evaluate for plural-sources OR logic)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    'value, data, expected',
    [
        pytest.param(True, SERVICE_DATA, True, id='has-value-present'),
        # Production ``IS NOT NULL`` treats '' as present — only NULL is "no value".
        pytest.param(True, {'Service': ''}, True, id='empty-string-is-present'),
        pytest.param(True, {}, False, id='missing-absent'),
        pytest.param(False, SERVICE_DATA, False, id='negated-present'),
        pytest.param(False, {}, True, id='negated-missing'),
        pytest.param(False, {'Service': ''}, False, id='negated-empty-string-is-present'),
    ],
)
def test_has_value_should_check_presence(value, data, expected):
    assert conditions.HasValue(value, source=Service()).evaluate(data) is expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'data, expected',
    [
        pytest.param({'Service': 'AmazonEC2', 'Account': '123'}, True, id='both-present'),
        pytest.param({'Service': 'AmazonEC2'}, True, id='first-present'),
        pytest.param({'Account': '123'}, True, id='second-present'),
        # Production ``IS NOT NULL`` treats '' as present — empty strings count as having value.
        pytest.param({'Service': '', 'Account': ''}, True, id='both-empty-strings-are-present'),
        pytest.param({}, False, id='both-missing'),
    ],
)
def test_has_value_with_sources_should_use_or_logic(data, expected):
    assert conditions.HasValue(sources=[Service(), Account()]).evaluate(data) is expected


@pytest.mark.unit
def test_sourced_condition_should_coerce_int_literal_to_string_for_match():
    # Production CFDL emits every literal as a SQL string and compares against
    # string-typed partition columns. An unquoted YAML scalar parsed as int (e.g. account ID)
    # must still match a string column. Coerce to str at construction.
    cond = conditions.Equals(123456789012, source=Account())  # int literal
    assert cond.evaluate({'Account': '123456789012'}) is True


@pytest.mark.unit
def test_sourced_condition_should_coerce_int_data_value_to_string_for_match():
    # The mirror case: column data supplied as int (e.g. via Python evaluation) compares as str.
    cond = conditions.Equals('123456789012', source=Account())
    assert cond.evaluate({'Account': 123456789012}) is True


@pytest.mark.unit
def test_sourced_condition_should_coerce_list_literal_elements_to_string():
    cond = conditions.Equals([123456789012, 210987654321], source=Account())
    assert cond.evaluate({'Account': '123456789012'}) is True
    assert cond.evaluate({'Account': '210987654321'}) is True
    assert cond.evaluate({'Account': '111111111111'}) is False


@pytest.mark.unit
def test_sourced_condition_should_apply_condition_level_transforms_to_single_source():
    # Production threads condition-level Transforms into the source ref before the comparison.
    cond = conditions.Equals('amazonec2', source=Service(), transforms=[Lower()])
    assert cond.evaluate({'Service': 'AmazonEC2'}) is True


@pytest.mark.unit
def test_sourced_condition_should_apply_condition_level_transforms_to_each_multi_source():
    cond = conditions.Equals('amazonec2', sources=[Service(), Account()], transforms=[Lower()])
    assert cond.evaluate({'Account': 'AmazonEC2'}) is True
    assert cond.evaluate({'Service': 'AmazonS3', 'Account': 'AMAZONEC2'}) is True


@pytest.mark.unit
def test_sourced_condition_split_nullif_should_make_match_false():
    # Out-of-range Split → '' → production NULLIF → NULL; comparison is FALSE.
    from costformation.transforms import Split

    cond = conditions.Equals('foo', source=Service(), transforms=[Split('|', 5)])
    assert cond.evaluate({'Service': 'a|b|c'}) is False


@pytest.mark.unit
def test_sourced_condition_split_nullif_should_skip_in_multi_source_or():
    from costformation.transforms import Split

    cond = conditions.Equals('foo', sources=[Service(), Account()], transforms=[Split('|', 5)])
    # Service Split is out-of-range (NULL) — gets skipped. Account Split lands on 'foo' — matches.
    assert cond.evaluate({'Service': 'a|b|c', 'Account': 'x|y|z|w|foo'}) is True


@pytest.mark.unit
def test_has_value_should_treat_split_out_of_range_as_no_value():
    # Production wraps Split in NULLIF(SPLIT_PART(...), '') — an out-of-range Split yields NULL,
    # so the condition-level Split makes HasValue see "no value" for that row.
    from costformation.transforms import Split

    cond = conditions.HasValue(True, source=Service(), transforms=[Split('|', 5)])
    assert cond.evaluate({'Service': 'a|b|c'}) is False
    assert cond.evaluate({'Service': 'a|b|c|d|e'}) is True


@pytest.mark.unit
def test_has_value_to_dict_should_include_value():
    assert conditions.HasValue(True, source=Service()).to_dict() == {'HasValue': True, 'Source': 'Service'}


@pytest.mark.unit
def test_has_value_evaluate_should_raise_without_source():
    with pytest.raises(ValueError, match='requires a source'):
        conditions.HasValue().evaluate({})


# ---------------------------------------------------------------------------
# ForDateRange
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_for_date_range_to_dict_should_nest_dates():
    assert conditions.ForDateRange('2025-01-01', '2025-12-31').to_dict() == {
        'ForDateRange': {'From': '2025-01-01', 'Until': '2025-12-31'}
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'usage_day, expected',
    [
        pytest.param('2025-06-15', True, id='within-range'),
        pytest.param('2025-01-01', True, id='inclusive-lower-bound'),
        pytest.param('2025-12-31', True, id='inclusive-upper-bound'),
        pytest.param('2024-12-31', False, id='before-range'),
        pytest.param('2026-01-01', False, id='after-range'),
    ],
)
def test_for_date_range_evaluate_should_check_usage_day_within_range(usage_day, expected):
    assert conditions.ForDateRange('2025-01-01', '2025-12-31').evaluate({'UsageDay': usage_day}) is expected


@pytest.mark.unit
def test_for_date_range_evaluate_should_return_false_when_usage_day_missing():
    assert conditions.ForDateRange('2025-01-01', '2025-12-31').evaluate({}) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    'start, end',
    [
        pytest.param('', '2025-12-31', id='missing-start'),
        pytest.param('2025-01-01', '', id='missing-end'),
    ],
)
def test_for_date_range_evaluate_should_return_false_when_either_date_empty(start, end):
    assert conditions.ForDateRange(start, end).evaluate({'UsageDay': '2025-06-15'}) is False


@pytest.mark.unit
def test_for_date_range_get_dependencies_should_return_usage_day():
    from costformation.core_dimensions import UsageDay

    deps = conditions.ForDateRange('2025-01-01', '2025-12-31').get_dependencies()
    assert len(deps) == 1
    assert isinstance(deps[0], UsageDay)


# ---------------------------------------------------------------------------
# End-to-end composition
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_operator_composition_should_evaluate_end_to_end():
    cond = (
        conditions.BeginsWith('Amazon', source=Service()) & ~conditions.Contains('S3', source=Service())
    ) | conditions.Equals('123', source=Account())
    assert cond.evaluate({'Service': 'AmazonEC2'}) is True
    assert cond.evaluate({'Service': 'AmazonS3'}) is False
    assert cond.evaluate({'Service': 'AmazonS3', 'Account': '123'}) is True
