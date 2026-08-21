# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
import yaml

from costformation import conditions, dimensions
from costformation.allocations import AllocationMethod, CostType, ElementCutoff, FixedRate, Granularity
from costformation.core_dimensions import Account, ProductFamily, Service, UsageFamily
from costformation.global_dimensions import ServiceDisplay
from costformation.rules import GroupByRule, GroupRule, MetadataRule
from costformation.transforms import Lower


class _TestGroup(dimensions.GroupDimension):
    source = Service()
    rules = [GroupRule('ec2', conditions.Equals('AmazonEC2'))]


class _TestAllocation(dimensions.AllocationDimension):
    streams = ['telemetry-stream-1']


@pytest.mark.unit
@pytest.mark.parametrize(
    'method, value, expected_cls',
    [
        pytest.param('equals', 'AmazonEC2', conditions.Equals, id='equals'),
        pytest.param('contains', 'EC2', conditions.Contains, id='contains'),
        pytest.param('begins_with', 'Amazon', conditions.BeginsWith, id='begins-with'),
        pytest.param('ends_with', 'EC2', conditions.EndsWith, id='ends-with'),
        pytest.param('matches', r'^Amazon', conditions.Matches, id='matches'),
        pytest.param('before', 'N', conditions.Before, id='before'),
        pytest.param('before_or_equals', 'N', conditions.BeforeOrEquals, id='before-or-equals'),
        pytest.param('after', 'A', conditions.After, id='after'),
        pytest.param('after_or_equals', 'A', conditions.AfterOrEquals, id='after-or-equals'),
    ],
)
def test_dimension_helper_should_produce_condition_bound_to_self(method, value, expected_cls):
    service = Service()
    condition = getattr(service, method)(value)
    assert isinstance(condition, expected_cls)
    assert condition.source is service


@pytest.mark.unit
def test_dimension_has_value_helper_should_produce_has_value_condition():
    service = Service()
    condition = service.has_value()
    assert isinstance(condition, conditions.HasValue)
    assert condition.value is True
    assert condition.source is service


@pytest.mark.unit
def test_dimension_has_value_helper_should_support_negation():
    assert Service().has_value(False).value is False


@pytest.mark.unit
def test_dimension_get_name_should_default_to_id():
    assert Service().get_name() == 'Service'


@pytest.mark.unit
def test_dimension_get_name_should_use_explicit_name_when_set():
    class Named(dimensions.CoreDimension):
        name = 'Pretty Name'

    assert Named().get_name() == 'Pretty Name'


@pytest.mark.unit
def test_group_dimension_get_id_should_use_explicit_id_when_set():
    # Use `id` when the desired dimension ID isn't a valid Python identifier —
    # e.g. hyphenated IDs like `cost-center`.
    class CostCenter(dimensions.GroupDimension):
        id = 'cost-center'

    assert CostCenter().get_id() == 'cost-center'
    assert CostCenter().get_reference() == 'User:Defined:cost-center'


@pytest.mark.unit
def test_allocation_dimension_get_id_should_use_explicit_id_when_set():
    class UnusedRISP(dimensions.AllocationDimension):
        id = 'unused-risp-allocation'
        streams = ['s1']

    assert UnusedRISP().get_id() == 'unused-risp-allocation'
    assert UnusedRISP().get_reference() == 'User:Defined:unused-risp-allocation'


@pytest.mark.unit
def test_core_dimension_get_reference_should_equal_id():
    dim = Service()
    assert dim.get_reference() == dim.get_id()


@pytest.mark.unit
def test_core_dimension_to_dict_should_raise():
    with pytest.raises(TypeError, match='cannot be serialized'):
        Service().to_dict()


@pytest.mark.unit
def test_global_dimension_reference_should_have_cz_prefix():
    assert ServiceDisplay().get_reference() == 'CZ:Defined:ServiceDisplay'


@pytest.mark.unit
def test_group_dimension_reference_should_have_user_prefix():
    assert _TestGroup().get_reference() == 'User:Defined:_TestGroup'


@pytest.mark.unit
def test_group_dimension_to_dict_should_omit_source_when_unset():
    class NoSource(dimensions.GroupDimension):
        rules = []

    assert 'Source' not in NoSource().to_dict()


@pytest.mark.unit
def test_group_dimension_to_dict_should_serialize_single_source():
    class Single(dimensions.GroupDimension):
        source = Service()
        rules = []

    assert Single().to_dict()['Source'] == 'Service'


@pytest.mark.unit
def test_group_dimension_to_dict_should_serialize_list_source():
    class Multi(dimensions.GroupDimension):
        source = [Service(), Account()]
        rules = []

    assert Multi().to_dict()['Source'] == ['Service', 'Account']


@pytest.mark.unit
def test_group_dimension_to_dict_should_omit_name_when_unset():
    assert 'Name' not in _TestGroup().to_dict()


@pytest.mark.unit
def test_group_dimension_to_dict_should_include_name_when_set():
    class Named(dimensions.GroupDimension):
        name = 'Display Name'
        source = Service()
        rules = []

    assert Named().to_dict()['Name'] == 'Display Name'


@pytest.mark.unit
def test_group_dimension_to_dict_should_include_rules():
    result = _TestGroup().to_dict()
    assert result['Rules'] == [{'Type': 'Group', 'Name': 'ec2', 'Conditions': [{'Equals': 'AmazonEC2'}]}]


@pytest.mark.unit
def test_group_dimension_to_dict_should_include_transforms_before_rules():
    class Transformed(dimensions.GroupDimension):
        source = Service()
        transforms = [Lower()]
        rules = []

    result = Transformed().to_dict()
    assert list(result.keys()).index('Transforms') < list(result.keys()).index('Rules')
    assert result['Transforms'] == [{'Type': 'Lower'}]


@pytest.mark.unit
@pytest.mark.parametrize(
    'attr, value, key',
    [
        pytest.param('default_value', 'Other', 'DefaultValue', id='default-value'),
        pytest.param('hide', True, 'Hide', id='hide'),
        pytest.param('disable', True, 'Disable', id='disable'),
    ],
)
def test_group_dimension_to_dict_should_include_optional_fields(attr, value, key):
    class Configured(dimensions.GroupDimension):
        source = Service()
        rules = []

    setattr(Configured, attr, value)
    assert Configured().to_dict()[key] == value


@pytest.mark.unit
def test_group_dimension_to_dict_should_serialize_child_and_override_as_references():
    class Parent(dimensions.GroupDimension):
        source = Service()
        rules = []
        child = Service()
        override = Account()

    result = Parent().to_dict()
    assert result['Child'] == 'Service'
    assert result['Override'] == 'Account'


@pytest.mark.unit
def test_group_dimension_evaluate_should_return_matched_rule_name():
    assert _TestGroup.evaluate({'Service': 'AmazonEC2'}) == 'ec2'


@pytest.mark.unit
def test_group_dimension_evaluate_should_return_default_when_no_match():
    class WithDefault(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('ec2', conditions.Equals('AmazonEC2'))]
        default_value = 'Other'

    assert WithDefault.evaluate({'Service': 'AmazonS3'}) == 'Other'


@pytest.mark.unit
def test_group_dimension_evaluate_should_return_none_when_no_match_and_no_default():
    assert _TestGroup.evaluate({'Service': 'AmazonS3'}) is None


@pytest.mark.unit
def test_group_dimension_evaluate_should_apply_dimension_transforms_before_rules():
    class Normalized(dimensions.GroupDimension):
        source = Service()
        transforms = [Lower()]
        rules = [GroupRule('ec2', conditions.Equals('amazonec2'))]

    assert Normalized.evaluate({'Service': 'AmazonEC2'}) == 'ec2'


@pytest.mark.unit
def test_group_dimension_evaluate_should_use_first_source_when_source_is_list():
    class MultiSource(dimensions.GroupDimension):
        source = [Service(), Account()]
        rules = [GroupRule('ec2', conditions.Equals('AmazonEC2'))]

    assert MultiSource.evaluate({'Service': 'AmazonEC2'}) == 'ec2'


@pytest.mark.unit
def test_group_dimension_evaluate_should_fire_rule_whose_condition_supplies_its_own_source():
    # When the dim has no source, a GroupRule whose condition specifies its own source
    # still resolves correctly — the rule isn't skipped just because the dim is sourceless.
    class NoSource(dimensions.GroupDimension):
        rules = [GroupRule('ec2', conditions.Equals('AmazonEC2', source=Service()))]

    assert NoSource.evaluate({'Service': 'AmazonEC2'}) == 'ec2'
    assert NoSource.evaluate({'Service': 'AmazonS3'}) is None


@pytest.mark.unit
def test_group_dimension_evaluate_should_apply_transforms_to_each_list_source_value():
    # When dim has source=[a, b] AND transforms=[X], production CFDL applies X
    # to *each* source value independently (not just the first). Rules then see
    # both transformed values for any sourceless conditions.
    class MultiSourceDim(dimensions.GroupDimension):
        source = [Service(), Account()]
        transforms = [Lower()]
        rules = [GroupRule('matched', conditions.Contains('aws', source=Account()))]

    # Without the fix, only Service was lowered; Account stayed uppercase and the
    # Contains('aws') would miss 'AWS-account-123'.
    assert MultiSourceDim.evaluate({'Service': 'EC2', 'Account': 'AWS-account-123'}) == 'matched'


@pytest.mark.unit
def test_group_dimension_evaluate_should_skip_transforms_when_source_value_missing():
    class Transformed(dimensions.GroupDimension):
        source = Service()
        transforms = [Lower()]
        rules = [GroupRule('ec2', conditions.Equals('amazonec2'))]

    assert Transformed.evaluate({}) is None


@pytest.mark.unit
def test_group_dimension_evaluate_should_use_group_by_rule_source_when_dimension_has_none():
    class Grouped(dimensions.GroupDimension):
        rules = [GroupByRule(source=Service())]

    assert Grouped.evaluate({'Service': 'AmazonEC2'}) == 'AmazonEC2'


@pytest.mark.unit
@pytest.mark.parametrize(
    'first_rule',
    [
        pytest.param(
            GroupByRule(source=Service(), conditions=[conditions.Equals('AmazonS3', source=Service())]),
            id='group-by-returns-none',
        ),
        pytest.param(MetadataRule(Service(), ['Lambda']), id='metadata-returns-none'),
    ],
)
def test_group_dimension_evaluate_should_continue_when_specialized_rule_returns_none(first_rule):
    class Cascade(dimensions.GroupDimension):
        source = Service()
        rules = [first_rule, GroupRule('ec2', conditions.Equals('AmazonEC2'))]

    assert Cascade.evaluate({'Service': 'AmazonEC2'}) == 'ec2'


@pytest.mark.unit
@pytest.mark.parametrize(
    'rule, expected',
    [
        pytest.param(GroupByRule(source=Service()), 'AmazonEC2', id='group-by-returns-source-value'),
        pytest.param(MetadataRule(Service(), ['EC2']), 'EC2', id='metadata-returns-substring-match'),
    ],
)
def test_group_dimension_evaluate_should_dispatch_specialized_rules(rule, expected):
    class Dim(dimensions.GroupDimension):
        source = Service()
        rules = [rule]

    assert Dim.evaluate({'Service': 'AmazonEC2'}) == expected


@pytest.mark.unit
def test_allocation_dimension_get_reference_should_use_user_defined_prefix():
    assert _TestAllocation().get_reference() == 'User:Defined:_TestAllocation'


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_always_include_type():
    assert _TestAllocation().to_dict()['Type'] == 'Allocation'


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_include_name_when_set():
    class Named(dimensions.AllocationDimension):
        name = 'Custom Name'
        streams = ['s1']

    assert Named().to_dict()['Name'] == 'Custom Name'


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_serialize_streams():
    assert _TestAllocation().to_dict()['AllocateByStreams'] == {'Streams': ['telemetry-stream-1']}


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_serialize_allocate_by_rules():
    class RuleBased(dimensions.AllocationDimension):
        allocation_method = AllocationMethod.PROPORTIONAL
        spend_to_allocate = [conditions.Equals('AmazonEC2', source=Service())]
        across_elements = [GroupRule('ec2', conditions.Equals('AmazonEC2'))]

    result = RuleBased().to_dict()
    rules = result['AllocateByRules']
    assert rules['AllocationMethod'] == 'Proportional'
    assert rules['SpendToAllocate'] == {'Conditions': [{'Equals': 'AmazonEC2', 'Source': 'Service'}]}
    assert rules['AcrossElements']['Rules'] == [{'Type': 'Group', 'Name': 'ec2', 'Conditions': [{'Equals': 'AmazonEC2'}]}]


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_include_rate_on_streams():
    class RateStreams(dimensions.AllocationDimension):
        streams = ['s1']
        rate = FixedRate(value=0.1, default_element='other')

    result = RateStreams().to_dict()
    assert result['AllocateByStreams'] == {
        'Streams': ['s1'],
        'Rate': {'Type': 'Fixed', 'Value': 0.1, 'DefaultElement': 'other'},
    }


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_emit_element_cutoff_at_top_level():
    class Cutoff(dimensions.AllocationDimension):
        streams = ['s1']
        element_cutoff = ElementCutoff(threshold_percent=5, name='Other')

    result = Cutoff().to_dict()
    assert result['ElementCutoff'] == {'ThresholdPercent': 5, 'Name': 'Other'}


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_emit_proportional_method_advanced_form():
    class Advanced(dimensions.AllocationDimension):
        allocation_method = dimensions.ProportionalMethod(
            granularity=Granularity.USAGE_DAILY,
            cost_type=CostType.REAL,
        )
        spend_to_allocate = dimensions.SpendToAllocate(conditions=[Service().equals('AmazonEC2')])
        across_elements = dimensions.AcrossElements(rules=[GroupRule(name='x', condition=Service().equals('AmazonEC2'))])

    result = Advanced().to_dict()
    assert result['AllocateByRules']['AllocationMethod'] == {
        'Method': 'Proportional',
        'Granularity': 'UsageDaily',
        'CostType': 'RealCost',
    }


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_emit_foreach_element_of_when_set():
    class ForEach(dimensions.AllocationDimension):
        allocation_method = AllocationMethod.PROPORTIONAL
        spend_to_allocate = [Service().equals('AmazonEC2')]
        across_elements = [GroupRule(name='x', condition=Service().equals('AmazonEC2'))]
        foreach_element_of = dimensions.ForEachElementOf(rules=[GroupRule(name='y', condition=Account().equals('123'))])

    block = ForEach().to_dict()['AllocateByRules']
    assert block['ForEachElementOf'] == {
        'Rules': [{'Type': 'Group', 'Name': 'y', 'Conditions': [{'Equals': '123', 'Source': 'Account'}]}]
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'attrs, message',
    [
        pytest.param(
            {
                'streams': ['s'],
                'allocation_method': AllocationMethod.PROPORTIONAL,
                'spend_to_allocate': [],
                'across_elements': [],
            },
            'cannot combine AllocateByStreams',
            id='streams-plus-method',
        ),
        pytest.param(
            {'allocation_method': AllocationMethod.PROPORTIONAL},
            'requires spend_to_allocate',
            id='method-without-spend-to-allocate',
        ),
        pytest.param(
            {'allocation_method': AllocationMethod.PROPORTIONAL, 'spend_to_allocate': []},
            'requires across_elements',
            id='method-without-across-elements',
        ),
        pytest.param(
            {
                'streams': ['s'],
                'rate': FixedRate(value=0.1, default_element='other'),
                'element_cutoff': ElementCutoff(threshold_percent=5),
            },
            'element_cutoff is not supported with rate-based',
            id='rate-plus-element-cutoff',
        ),
        pytest.param(
            {
                'allocation_method': AllocationMethod.EVEN,
                'spend_to_allocate': [],
                'across_elements': [GroupRule(name='x', condition=Service().equals('AmazonEC2'))],
                'element_cutoff': ElementCutoff(threshold_percent=5),
            },
            'element_cutoff is not supported with Even',
            id='even-plus-element-cutoff',
        ),
        pytest.param(
            {
                'allocation_method': AllocationMethod.EVEN,
                'spend_to_allocate': [],
                'across_elements': [GroupRule(name='x', condition=Service().equals('AmazonEC2'))],
                'foreach_element_of': dimensions.ForEachElementOf(
                    rules=[GroupRule(name='y', condition=Account().equals('123'))]
                ),
            },
            'foreach_element_of requires Proportional',
            id='foreach-without-proportional',
        ),
    ],
)
def test_allocation_dimension_should_raise_on_invalid_combinations(attrs, message):
    cls = type('BadAllocation', (dimensions.AllocationDimension,), attrs)
    with pytest.raises(ValueError, match=message):
        cls().to_dict()


@pytest.mark.unit
def test_allocation_dimension_to_dict_should_include_hide_and_disable_when_set():
    class Hidden(dimensions.AllocationDimension):
        hide = True
        disable = True
        streams = ['s1']

    result = Hidden().to_dict()
    assert result['Hide'] is True
    assert result['Disable'] is True


@pytest.mark.unit
def test_allocation_dimension_evaluate_should_raise():
    with pytest.raises(TypeError, match='_TestAllocation cannot be evaluated'):
        _TestAllocation.evaluate({'Service': 'AmazonEC2'})


@pytest.mark.unit
def test_cost_formation_evaluate_should_raise_when_target_dimension_missing():
    cf = dimensions.CostFormation([_TestGroup()])
    with pytest.raises(ValueError, match="'NotThere' is not in this CostFormation"):
        cf.evaluate({'Service': 'AmazonEC2'}, 'NotThere')


@pytest.mark.unit
def test_cost_formation_evaluate_should_return_value_for_dimension_with_no_dependencies():
    cf = dimensions.CostFormation([_TestGroup()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, '_TestGroup') == 'ec2'


@pytest.mark.unit
def test_cost_formation_evaluate_should_prefer_input_value_over_evaluating_internal_dimension():
    cf = dimensions.CostFormation([_TestGroup()])
    assert cf.evaluate({'Service': 'AmazonEC2', '_TestGroup': 'overridden'}, '_TestGroup') == 'overridden'


@pytest.mark.unit
def test_cost_formation_evaluate_should_use_input_value_for_upstream_dependency():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('would-not-match', conditions.Equals('AmazonS3'))]

    class Downstream(dimensions.GroupDimension):
        source = Upstream()
        rules = [GroupRule('matched', Upstream().equals('precomputed'))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2', 'Upstream': 'precomputed'}, 'Downstream') == 'matched'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_upstream_dimension_in_formation():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('compute', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Upstream()
        rules = [GroupRule('matched', Upstream().equals('compute'))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, 'Downstream') == 'matched'


@pytest.mark.unit
def test_cost_formation_evaluate_should_treat_external_references_as_inputs():
    class FromTag(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    cf = dimensions.CostFormation([FromTag()])
    assert cf.evaluate({'Service': 'AmazonS3'}, 'FromTag') is None


@pytest.mark.unit
def test_cost_formation_evaluate_should_raise_when_required_input_missing():
    cf = dimensions.CostFormation([_TestGroup()])
    with pytest.raises(ValueError, match="Required input 'Service' was not provided"):
        cf.evaluate({}, '_TestGroup')


@pytest.mark.unit
def test_cost_formation_evaluate_should_return_none_for_missing_input_when_allowed():
    cf = dimensions.CostFormation([_TestGroup()])
    assert cf.evaluate({}, '_TestGroup', allow_missing_inputs=True) is None


@pytest.mark.unit
def test_cost_formation_evaluate_should_propagate_none_upstream_value_to_downstream_data():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('only-s3', conditions.Equals('AmazonS3'))]

    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('upstream-empty', conditions.HasValue(False, source=Upstream()))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, 'Downstream') == 'upstream-empty'


@pytest.mark.unit
def test_cost_formation_evaluate_should_raise_on_cycle():
    class A(dimensions.GroupDimension):
        rules: list = []

    class B(dimensions.GroupDimension):
        source = A()
        rules: list = []

    A.source = B()  # close the cycle after both classes exist
    with pytest.raises(ValueError, match='Cycle detected'):
        dimensions.CostFormation([A(), B()]).evaluate({}, 'A')


@pytest.mark.unit
def test_cost_formation_evaluate_should_raise_when_target_is_allocation_and_inputs_required():
    cf = dimensions.CostFormation([_TestAllocation()])
    with pytest.raises(ValueError, match='cannot be evaluated'):
        cf.evaluate({}, '_TestAllocation')


@pytest.mark.unit
def test_cost_formation_evaluate_should_treat_allocation_as_none_when_allow_missing_inputs():
    # Allocation dims can't be computed — under allow_missing_inputs they resolve
    # to None instead of raising, so transitive chains don't blow up.
    cf = dimensions.CostFormation([_TestAllocation()])
    assert cf.evaluate({}, '_TestAllocation', allow_missing_inputs=True) is None


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_referenced_via_not():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('inverse', ~Upstream().equals('match'))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonS3'}, 'Downstream') == 'inverse'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_referenced_via_plural_sources():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('any-has-value', conditions.HasValue(sources=[Upstream(), Account()]))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, 'Downstream') == 'any-has-value'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_referenced_via_rule_source_override():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('overridden', conditions.Equals('match'), source=Upstream())]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, 'Downstream') == 'overridden'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_referenced_via_list_source():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = [Upstream(), Service()]
        rules = [GroupRule('matched', Upstream().equals('match'))]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, 'Downstream') == 'matched'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_in_metadata_rule_conditions():
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [MetadataRule(Service(), ['EC2'], conditions=[Upstream().equals('match')])]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2'}, 'Downstream') == 'EC2'


@pytest.mark.unit
@pytest.mark.parametrize(
    'data_key',
    [
        pytest.param('UsageFamily', id='usage-family-key'),
        pytest.param('ProductFamily', id='product-family-key'),
    ],
)
def test_group_dimension_evaluate_should_treat_usage_family_and_product_family_as_aliases(data_key):
    # Production maps both names to the same underlying partition column.
    class FamilyGroup(dimensions.GroupDimension):
        source = ProductFamily()
        rules = [GroupRule('compute', conditions.Equals('Compute'))]

    assert FamilyGroup.evaluate({data_key: 'Compute'}) == 'compute'


@pytest.mark.unit
@pytest.mark.parametrize(
    'data_key',
    [
        pytest.param('UsageFamily', id='usage-family-key'),
        pytest.param('ProductFamily', id='product-family-key'),
    ],
)
def test_group_dimension_evaluate_should_alias_in_reverse_direction(data_key):
    class FamilyGroup(dimensions.GroupDimension):
        source = UsageFamily()
        rules = [GroupRule('storage', conditions.Equals('Storage'))]

    assert FamilyGroup.evaluate({data_key: 'Storage'}) == 'storage'


@pytest.mark.unit
def test_cost_formation_evaluate_should_alias_usage_family_and_product_family_in_inputs():
    # Caller passes UsageFamily; a downstream dim depends on ProductFamily — should still resolve.
    class FamilyGroup(dimensions.GroupDimension):
        source = ProductFamily()
        rules = [GroupRule('compute', conditions.Equals('Compute'))]

    cf = dimensions.CostFormation([FamilyGroup()])
    assert cf.evaluate({'UsageFamily': 'Compute'}, 'FamilyGroup') == 'compute'


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_for_date_range_dependency_on_usage_day():
    # ForDateRange unpacks to a Between on UsageDay in production; CostFormation must thread the
    # UsageDay input through to the condition's evaluate.
    class DateGated(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('in-range', conditions.ForDateRange('2025-01-01', '2025-12-31'))]

    cf = dimensions.CostFormation([DateGated()])
    in_range = cf.evaluate({'Service': 'AmazonEC2', 'UsageDay': '2025-06-15'}, 'DateGated')
    out_of_range = cf.evaluate({'Service': 'AmazonEC2', 'UsageDay': '2024-12-31'}, 'DateGated')
    assert in_range == 'in-range'
    assert out_of_range is None


@pytest.mark.unit
def test_cost_formation_evaluate_should_resolve_dependency_in_group_by_rule_coalesce_sources():
    # Multi-source non-coalesce now requires ALL sources, so this case uses CoalesceSources to
    # keep the original "first non-null" semantics.
    class Upstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupRule('match', conditions.Equals('AmazonEC2'))]

    class Downstream(dimensions.GroupDimension):
        source = Upstream()
        rules = [GroupByRule(sources=[Upstream(), Account()], coalesce_sources=True)]

    cf = dimensions.CostFormation([Upstream(), Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, 'Downstream') == 'match'


@pytest.mark.unit
def test_cost_formation_evaluate_should_concat_non_coalesce_group_by_sources():
    # Multi-source non-coalesce concatenates via the format (default '{0} {1}').
    class Downstream(dimensions.GroupDimension):
        source = Service()
        rules = [GroupByRule(sources=[Service(), Account()])]

    cf = dimensions.CostFormation([Downstream()])
    assert cf.evaluate({'Service': 'AmazonEC2', 'Account': '123'}, 'Downstream') == 'AmazonEC2 123'


@pytest.mark.unit
def test_cost_formation_to_dict_should_key_by_dimension_id():
    cf = dimensions.CostFormation([_TestGroup()])
    assert cf.to_dict() == {'Dimensions': {'_TestGroup': _TestGroup().to_dict()}}


@pytest.mark.unit
def test_cost_formation_to_yaml_should_round_trip_via_yaml_loader():
    cf = dimensions.CostFormation([_TestGroup()])
    loaded = yaml.safe_load(cf.to_yaml())
    assert loaded == cf.to_dict()


@pytest.mark.unit
def test_cost_formation_to_yaml_should_preserve_insertion_order():
    class Alpha(dimensions.GroupDimension):
        source = Service()
        rules = []

    class Beta(dimensions.GroupDimension):
        source = Service()
        rules = []

    cf = dimensions.CostFormation([Alpha(), Beta()])
    rendered = cf.to_yaml()
    assert rendered.index('Alpha:') < rendered.index('Beta:')
