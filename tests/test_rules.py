# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation.conditions import And, BeginsWith, Contains, Equals, HasValue, Or
from costformation.core_dimensions import Account, Region, Service
from costformation.rules import GroupByRule, GroupRule, MetadataRule, Rule
from costformation.transforms import Lower, Normalize


@pytest.mark.unit
@pytest.mark.parametrize(
    'rule_cls, kwargs',
    [
        pytest.param(GroupRule, {'name': 'ec2', 'condition': Equals('AmazonEC2')}, id='group-rule'),
        pytest.param(GroupByRule, {'source': Service()}, id='group-by-rule'),
        pytest.param(MetadataRule, {'source': Service(), 'values': ['EC2']}, id='metadata-rule'),
    ],
)
def test_concrete_rule_should_be_instance_of_rule_base(rule_cls, kwargs):
    assert isinstance(rule_cls(**kwargs), Rule)


@pytest.mark.unit
def test_rule_should_not_be_directly_instantiable():
    with pytest.raises(TypeError, match='abstract'):
        Rule()


@pytest.mark.unit
def test_metadata_rule_should_not_accept_transforms_kwarg():
    with pytest.raises(TypeError, match='transforms'):
        MetadataRule(Service(), ['EC2'], transforms=[Lower()])


@pytest.mark.unit
def test_group_rule_to_dict_should_wrap_single_condition_in_list():
    result = GroupRule('ec2', Equals('AmazonEC2')).to_dict()
    assert result == {'Type': 'Group', 'Name': 'ec2', 'Conditions': [{'Equals': 'AmazonEC2'}]}


@pytest.mark.unit
def test_group_rule_to_dict_should_flatten_top_level_or_to_condition_list():
    condition = Or(Equals('AmazonEC2'), Equals('AmazonS3'))
    result = GroupRule('compute-or-storage', condition).to_dict()
    assert result == {
        'Type': 'Group',
        'Name': 'compute-or-storage',
        'Conditions': [{'Equals': 'AmazonEC2'}, {'Equals': 'AmazonS3'}],
    }


@pytest.mark.unit
def test_group_rule_to_dict_should_keep_top_level_and_wrapped_as_single_condition():
    condition = And(BeginsWith('Amazon'), Contains('EC2'))
    result = GroupRule('amazon-ec2', condition).to_dict()
    assert result['Conditions'] == [{'And': [{'BeginsWith': 'Amazon'}, {'Contains': 'EC2'}]}]


@pytest.mark.unit
def test_group_rule_to_dict_should_include_source_when_set():
    result = GroupRule('ec2', Equals('AmazonEC2'), source=Service()).to_dict()
    assert result['Source'] == 'Service'


@pytest.mark.unit
def test_group_rule_to_dict_should_include_transforms_when_set():
    result = GroupRule('ec2', Equals('amazonec2'), transforms=[Lower()]).to_dict()
    assert result['Transforms'] == [{'Type': 'Lower'}]


@pytest.mark.unit
def test_group_rule_evaluate_should_use_dimension_source_when_rule_source_unset():
    rule = GroupRule('ec2', Equals('AmazonEC2'))
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'ec2'


@pytest.mark.unit
def test_group_rule_evaluate_should_prefer_rule_source_over_dimension_source():
    rule = GroupRule('us-east', Equals('us-east-1'), source=Region())
    assert rule.evaluate({'Region': 'us-east-1', 'Service': 'AmazonEC2'}, Service()) == 'us-east'


@pytest.mark.unit
def test_group_rule_evaluate_should_apply_transforms_before_condition():
    rule = GroupRule('ec2', Equals('amazonec2'), source=Service(), transforms=[Lower()])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'ec2'


@pytest.mark.unit
def test_group_rule_evaluate_should_use_condition_source_when_no_dim_or_rule_source():
    # CFDL: a GroupRule whose condition supplies its own source can fire even when
    # neither the dim nor the rule has one.
    rule = GroupRule('match', Service().equals('AmazonEC2'))
    assert rule.evaluate({'Service': 'AmazonEC2'}, None) == 'match'
    assert rule.evaluate({'Service': 'AmazonS3'}, None) is None


@pytest.mark.unit
def test_group_rule_evaluate_with_empty_name_should_return_transformed_source_value():
    # CFDL: name='' on a Group rule means "use the (transformed) source value as the
    # dynamic group name" — folds GroupBy-with-gating into a single rule. Note the
    # condition runs against the post-transform value.
    rule = GroupRule('', Equals('snowflakecompute', source=Service()), source=Service(), transforms=[Lower()])
    assert rule.evaluate({'Service': 'SnowflakeCompute'}, None) == 'snowflakecompute'


@pytest.mark.unit
def test_group_rule_evaluate_with_empty_name_and_no_source_returns_none():
    rule = GroupRule('', Service().equals('AmazonEC2'))
    assert rule.evaluate({'Service': 'AmazonEC2'}, None) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    'condition, data, expected',
    [
        pytest.param(
            And(BeginsWith('Amazon'), Contains('EC2')),
            {'Service': 'AmazonEC2'},
            'test',
            id='and-both-match',
        ),
        pytest.param(
            And(BeginsWith('Amazon'), Contains('EC2')),
            {'Service': 'AmazonS3'},
            None,
            id='and-one-miss',
        ),
        pytest.param(
            Or(Equals('AmazonEC2'), Equals('AmazonS3')),
            {'Service': 'AmazonS3'},
            'test',
            id='or-one-match',
        ),
        pytest.param(
            Or(Equals('AmazonEC2'), Equals('AmazonS3')),
            {'Service': 'AmazonRDS'},
            None,
            id='or-no-match',
        ),
    ],
)
def test_group_rule_evaluate_should_recurse_into_logical_operators(condition, data, expected):
    assert GroupRule('test', condition).evaluate(data, Service()) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'kwargs, message',
    [
        pytest.param({}, 'requires either source or sources', id='no-source'),
        pytest.param(
            {'source': Service(), 'sources': [Account()]},
            'Cannot specify both',
            id='both-source-and-sources',
        ),
    ],
)
def test_group_by_rule_should_raise_for_invalid_source_kwargs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        GroupByRule(**kwargs)


@pytest.mark.unit
@pytest.mark.parametrize(
    'kwargs, expected_extras',
    [
        pytest.param({'source': Service()}, {'Source': 'Service'}, id='single-source'),
        pytest.param(
            {'source': [Service(), Account()]},
            {'Source': ['Service', 'Account']},
            id='list-source-as-yaml-list',
        ),
        pytest.param({'sources': [Service()]}, {'Sources': ['Service']}, id='single-element-sources'),
        pytest.param({'sources': [Service(), Account()]}, {'Sources': ['Service', 'Account']}, id='multiple-sources'),
    ],
)
def test_group_by_rule_to_dict_should_serialize_source_kwargs(kwargs, expected_extras):
    assert GroupByRule(**kwargs).to_dict() == {'Type': 'GroupBy', **expected_extras}


@pytest.mark.unit
@pytest.mark.parametrize(
    'coalesce, expected_present',
    [
        pytest.param(True, True, id='flag-set'),
        pytest.param(False, False, id='flag-omitted-when-false'),
    ],
)
def test_group_by_rule_to_dict_should_emit_coalesce_only_when_true(coalesce, expected_present):
    result = GroupByRule(sources=[Service(), Account()], coalesce_sources=coalesce).to_dict()
    assert ('CoalesceSources' in result) is expected_present


@pytest.mark.unit
def test_group_by_rule_to_dict_should_include_transforms_conditions_and_format():
    result = GroupByRule(
        source=Service(),
        transforms=[Lower()],
        conditions=[HasValue(source=Service())],
        format='svc: {0}',
    ).to_dict()
    assert result['Transforms'] == [{'Type': 'Lower'}]
    assert result['Conditions'] == [{'HasValue': True, 'Source': 'Service'}]
    assert result['Format'] == 'svc: {0}'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_return_source_value():
    assert GroupByRule(source=Service()).evaluate({'Service': 'AmazonEC2'}, Service()) == 'AmazonEC2'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_concat_sources_via_default_format_when_source_is_list():
    # Production: ``Source: [A, B]`` (list, non-coalesce) → ``concat(NVL(A, ''), ' ', NVL(B, ''))``.
    # Default format from production is ``' '.join('{i}' for i in range(num_sources))``.
    rule = GroupByRule(source=[Service(), Account()])
    assert rule.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, Service()) == 'AmazonEC2 123'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_apply_format_when_source_is_list():
    rule = GroupByRule(source=[Service(), Account()], format='{0}/{1}')
    assert rule.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, Service()) == 'AmazonEC2/123'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_return_none_when_any_non_coalesce_source_missing():
    # Production: ``WHEN HasValue(A) AND HasValue(B) THEN ...`` — every source must have a value.
    rule = GroupByRule(source=[Service(), Account()])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) is None
    assert rule.evaluate({'Account': '123'}, Service()) is None


@pytest.mark.unit
def test_group_by_rule_evaluate_should_apply_format_to_value():
    rule = GroupByRule(source=Service(), format='svc: {0}')
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'svc: AmazonEC2'


@pytest.mark.unit
@pytest.mark.parametrize(
    'transforms, value, expected',
    [
        pytest.param([Lower()], 'AmazonEC2', 'amazonec2', id='lower'),
        # Normalize matches production CFDL: trim only whitespace — dashes from
        # space-translation at the edges remain.
        pytest.param([Normalize()], '  Amazon EC2  ', '--amazon-ec2--', id='normalize'),
    ],
)
def test_group_by_rule_evaluate_should_apply_transforms(transforms, value, expected):
    rule = GroupByRule(source=Service(), transforms=transforms)
    assert rule.evaluate({'Service': value}, Service()) == expected


@pytest.mark.unit
def test_group_by_rule_evaluate_should_coalesce_sources_in_order_when_coalesce_flag_set():
    # Production COALESCE semantics: only fires when CoalesceSources: True is set.
    rule = GroupByRule(sources=[Service(), Account()], coalesce_sources=True)
    assert rule.evaluate({'Account': '123'}, Service()) == '123'
    assert rule.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, Service()) == 'AmazonEC2'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_return_none_when_all_coalesce_sources_missing():
    rule = GroupByRule(sources=[Service(), Account()], coalesce_sources=True)
    assert rule.evaluate({}, Service()) is None


@pytest.mark.unit
def test_group_by_rule_evaluate_should_require_all_non_coalesce_sources_have_value():
    # Without CoalesceSources, production requires HasValue(A) AND HasValue(B).
    rule = GroupByRule(sources=[Service(), Account()])
    assert rule.evaluate({'Account': '123'}, Service()) is None
    assert rule.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, Service()) == 'AmazonEC2 123'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_return_none_when_source_missing():
    assert GroupByRule(source=Service()).evaluate({}, Service()) is None


@pytest.mark.unit
def test_group_by_rule_evaluate_should_pass_through_empty_source_value():
    # Production ``IS NOT NULL`` treats '' as present — only NULL is missing — so the rule fires
    # and returns the (post-format) empty string. (NULL only arises from out-of-range Split.)
    assert GroupByRule(source=Service()).evaluate({'Service': ''}, Service()) == ''


@pytest.mark.unit
def test_group_by_rule_evaluate_should_treat_post_transform_empty_as_no_match():
    # Production's NULLIF(SPLIT_PART(...), '') turns out-of-range Split into NULL.
    # Mirror that: a transform chain that produces '' (e.g. Split index past end)
    # is no-match.
    from costformation.transforms import Split

    rule = GroupByRule(source=Service(), transforms=[Split(delimiter='|', index=5)])
    assert rule.evaluate({'Service': 'a|b|c'}, Service()) is None


@pytest.mark.unit
def test_group_by_rule_evaluate_should_return_none_when_conditions_unmet():
    rule = GroupByRule(source=Service(), conditions=[Equals('AmazonS3', source=Service())])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) is None


@pytest.mark.unit
def test_group_by_rule_evaluate_should_prefer_rule_source_over_dim_source_for_gating():
    # Sourceless gating condition should resolve against the rule's source (Region),
    # not the dim fallback (Service) — so 'us-east-1' should match.
    rule = GroupByRule(source=Region(), conditions=[Equals('us-east-1')])
    data = {'Region': 'us-east-1', 'Service': 'AmazonEC2'}
    assert rule.evaluate(data, Service()) == 'us-east-1'


@pytest.mark.unit
@pytest.mark.parametrize(
    'kwargs, message',
    [
        pytest.param({'values': ['EC2']}, 'either source or sources', id='no-source'),
        pytest.param({'source': Service()}, 'requires values', id='no-values'),
        pytest.param(
            {'source': Service(), 'values': ['EC2'], 'sources': [Account()]},
            'Cannot specify both',
            id='both-source-and-sources',
        ),
    ],
)
def test_metadata_rule_should_raise_for_invalid_kwargs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        MetadataRule(**kwargs)


@pytest.mark.unit
@pytest.mark.parametrize(
    'source, expected_source_field',
    [
        pytest.param(Service(), 'Service', id='single-source-as-string'),
        pytest.param([Service(), Account()], ['Service', 'Account'], id='list-source-as-list'),
    ],
)
def test_metadata_rule_to_dict_should_serialize_source(source, expected_source_field):
    result = MetadataRule(source, ['EC2']).to_dict()
    assert result['Source'] == expected_source_field


@pytest.mark.unit
def test_metadata_rule_to_dict_should_serialize_sources_kwarg_with_coalesce():
    result = MetadataRule(values=['EC2'], sources=[Service(), Account()], coalesce_sources=True).to_dict()
    assert result['Sources'] == ['Service', 'Account']
    assert result['CoalesceSources'] is True


@pytest.mark.unit
def test_metadata_rule_to_dict_should_include_optional_fields():
    result = MetadataRule(
        Service(),
        ['EC2'],
        format='matched: {0}',
        conditions=[HasValue(source=Service())],
    ).to_dict()
    assert result['Format'] == 'matched: {0}'
    assert result['Conditions'] == [{'HasValue': True, 'Source': 'Service'}]


@pytest.mark.unit
def test_metadata_rule_evaluate_should_return_matched_substring():
    rule = MetadataRule(Service(), ['EC2', 'S3'])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'EC2'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_return_none_when_no_match():
    rule = MetadataRule(Service(), ['Lambda'])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) is None


@pytest.mark.unit
def test_metadata_rule_evaluate_should_skip_missing_sources():
    rule = MetadataRule([Service(), Account()], ['123'])
    assert rule.evaluate({'Account': '123'}, Service()) == '123'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_iterate_sources_kwarg():
    rule = MetadataRule(values=['123'], sources=[Service(), Account()])
    assert rule.evaluate({'Account': '123'}, Service()) == '123'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_apply_format_to_match():
    rule = MetadataRule(Service(), ['EC2'], format='service: {0}')
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'service: EC2'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_resolve_hierarchical_pattern_to_output_name():
    rule = MetadataRule(Service(), [{'compute': ['EC2', 'Lambda']}])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'compute'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_format_hierarchical_output_name():
    rule = MetadataRule(Service(), [{'compute': ['EC2']}], format='group: {0}')
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'group: compute'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_return_none_when_conditions_unmet():
    rule = MetadataRule(Service(), ['EC2'], conditions=[Equals('AmazonS3', source=Service())])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) is None


@pytest.mark.unit
def test_metadata_rule_evaluate_should_match_after_passing_condition():
    rule = MetadataRule(Service(), ['EC2'], conditions=[Equals('AmazonEC2', source=Service())])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'EC2'


@pytest.mark.unit
def test_metadata_rule_evaluate_hierarchical_should_skip_match_strings_until_one_matches():
    rule = MetadataRule(Service(), [{'compute': ['Lambda', 'EC2']}])
    assert rule.evaluate({'Service': 'AmazonEC2'}, Service()) == 'compute'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_normalize_underscores_to_dashes_in_source():
    # CFDL: source is normalized — special chars (incl. _) → '-'.
    # 'prod_live_application' normalizes to 'prod-live-application' → matches '-application' pattern.
    rule = MetadataRule(Service(), ['-application'])
    assert rule.evaluate({'Service': 'prod_live_application'}, Service()) == 'application'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_strip_leading_trailing_dashes_from_output():
    # Pattern '-foo-' returns 'foo' (dashes are matching markers, stripped on emit).
    rule = MetadataRule(Service(), ['-application-'])
    assert rule.evaluate({'Service': 'prod_live_application_high'}, Service()) == 'application'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_match_case_insensitively():
    rule = MetadataRule(Service(), ['Frontend'])
    assert rule.evaluate({'Service': 'frontend-service'}, Service()) == 'Frontend'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_return_pattern_with_internal_dashes_unchanged():
    # 'application-high' has no leading/trailing dash, returned as-is on match.
    rule = MetadataRule(Service(), ['application-high', '-application'])
    # Order matters: 'application-high' is checked first.
    assert rule.evaluate({'Service': 'prod_live_application_high'}, Service()) == 'application-high'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_match_at_word_boundary_via_dash_wrapping():
    # Source 'prod_live_application' wraps to '-prod-live-application-'.
    # Pattern '-application' must match suffix word, not the middle of a longer word.
    rule = MetadataRule(Service(), ['-application'])
    # 'reapplication' wraps to '-reapplication-' — '-application' is NOT a substring.
    assert rule.evaluate({'Service': 'reapplication'}, Service()) is None
    # 'prod_application' wraps to '-prod-application-' — '-application' IS a substring (suffix word).
    assert rule.evaluate({'Service': 'prod_application'}, Service()) == 'application'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_iterate_patterns_before_sources():
    # Production unrolls Metadata into one Group rule per value_group, in order — so an earlier
    # pattern matching ANY source wins over a later pattern that matches a different source.
    rule = MetadataRule(source=[Service(), Account()], values=['p1', 'p2'])
    data = {'Service': 'has-p2', 'Account': 'has-p1'}
    assert rule.evaluate(data, Service()) == 'p1'


@pytest.mark.unit
def test_metadata_rule_evaluate_should_match_hierarchical_pattern_across_sources():
    # Hierarchical pattern compiles to Contains([norm(key), norm(match1), ...]); production OR's
    # the Contains across all sources, so any source matching any term yields the output_name.
    rule = MetadataRule(sources=[Service(), Account()], values=[{'compute': ['EC2', 'Lambda']}])
    assert rule.evaluate({'Account': 'lambda-runner'}, Service()) == 'compute'


@pytest.mark.unit
def test_group_rule_evaluate_should_treat_split_nullif_as_no_match_for_has_value_condition():
    # Production wraps Split in NULLIF(SPLIT_PART(...), ''), so a HasValue condition over a
    # rule whose transforms include an out-of-range Split sees NULL and returns FALSE.
    from costformation.transforms import Split

    rule = GroupRule('matched', HasValue(), source=Service(), transforms=[Split('|', 5)])
    assert rule.evaluate({'Service': 'a|b|c'}, None) is None
    assert rule.evaluate({'Service': 'a|b|c|d|e'}, None) == 'matched'


@pytest.mark.unit
def test_group_by_rule_evaluate_should_propagate_split_nullif_in_multi_source_non_coalesce():
    from costformation.transforms import Split

    rule = GroupByRule(sources=[Service(), Account()], transforms=[Split('|', 5)])
    data = {'Service': 'a|b|c|d|e', 'Account': 'too|short'}
    assert rule.evaluate(data, None) is None


@pytest.mark.unit
def test_metadata_rule_evaluate_should_prefer_rule_source_over_dim_source_for_gating():
    # Sourceless gating condition resolves against rule source (Region), not dim fallback (Service).
    rule = MetadataRule(Region(), ['us-east'], conditions=[Equals('us-east-1')])
    data = {'Region': 'us-east-1', 'Service': 'AmazonEC2'}
    assert rule.evaluate(data, Service()) == 'us-east'
