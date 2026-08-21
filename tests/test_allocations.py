# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation.allocations import (
    AllocationMethod,
    CostType,
    ElementCutoff,
    FixedRate,
    Granularity,
    ProportionalMethod,
)
from costformation.conditions import Equals, HasValue
from costformation.core_dimensions import Account, Service
from costformation.dimensions import AcrossElements, ForEachElementOf, SpendToAllocate
from costformation.rules import GroupByRule, GroupRule
from costformation.transforms import Lower


@pytest.mark.unit
@pytest.mark.parametrize(
    'member, expected_value',
    [
        pytest.param(AllocationMethod.PROPORTIONAL, 'Proportional', id='proportional'),
        pytest.param(AllocationMethod.EVEN, 'Even', id='even'),
    ],
)
def test_allocation_method_values(member, expected_value):
    assert member.value == expected_value


@pytest.mark.unit
def test_proportional_method_to_dict_should_emit_only_method_when_unconfigured():
    assert ProportionalMethod().to_dict() == {'Method': 'Proportional'}


@pytest.mark.unit
def test_proportional_method_to_dict_should_include_granularity_when_set():
    result = ProportionalMethod(granularity=Granularity.BILLING_PERIOD).to_dict()
    assert result == {'Method': 'Proportional', 'Granularity': 'BillingPeriod'}


@pytest.mark.unit
def test_proportional_method_to_dict_should_include_cost_type_when_set():
    result = ProportionalMethod(cost_type=CostType.REAL).to_dict()
    assert result == {'Method': 'Proportional', 'CostType': 'RealCost'}


@pytest.mark.unit
def test_proportional_method_to_dict_should_include_both_granularity_and_cost_type():
    result = ProportionalMethod(granularity=Granularity.USAGE_MONTHLY, cost_type=CostType.AMORTIZED).to_dict()
    assert result == {
        'Method': 'Proportional',
        'Granularity': 'UsageMonthly',
        'CostType': 'AmortizedCost',
    }


@pytest.mark.unit
def test_fixed_rate_to_dict_should_emit_type_value_and_default_element():
    assert FixedRate(value=0.5, default_element='other').to_dict() == {
        'Type': 'Fixed',
        'Value': 0.5,
        'DefaultElement': 'other',
    }


@pytest.mark.unit
def test_element_cutoff_to_dict_should_omit_name_when_unset():
    assert ElementCutoff(threshold_percent=5).to_dict() == {'ThresholdPercent': 5}


@pytest.mark.unit
def test_element_cutoff_to_dict_should_include_name_when_set():
    assert ElementCutoff(threshold_percent=5, name='Other').to_dict() == {
        'ThresholdPercent': 5,
        'Name': 'Other',
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'percent',
    [pytest.param(-1, id='negative'), pytest.param(100, id='at-max'), pytest.param(150, id='above-max')],
)
def test_element_cutoff_should_raise_for_threshold_out_of_range(percent):
    with pytest.raises(ValueError, match=r'threshold_percent must be in \[0, 100\)'):
        ElementCutoff(threshold_percent=percent)


@pytest.mark.unit
def test_spend_to_allocate_to_dict_should_serialize_conditions_only():
    block = SpendToAllocate(conditions=[Equals('AmazonEC2', source=Service())])
    assert block.to_dict() == {'Conditions': [{'Equals': 'AmazonEC2', 'Source': 'Service'}]}


@pytest.mark.unit
def test_spend_to_allocate_to_dict_should_serialize_full_source_info_block():
    block = SpendToAllocate(
        source=Service(),
        transforms=[Lower()],
        conditions=[Equals('amazonec2', source=Service())],
    )
    assert block.to_dict() == {
        'Source': 'Service',
        'Transforms': [{'Type': 'Lower'}],
        'Conditions': [{'Equals': 'amazonec2', 'Source': 'Service'}],
    }


@pytest.mark.unit
def test_spend_to_allocate_to_dict_should_use_sources_when_plural_specified():
    block = SpendToAllocate(sources=[Service(), Account()], coalesce_sources=True)
    assert block.to_dict() == {'Sources': ['Service', 'Account'], 'CoalesceSources': True}


@pytest.mark.unit
def test_spend_to_allocate_should_raise_when_both_source_and_sources_given():
    with pytest.raises(ValueError, match='Cannot specify both source and sources'):
        SpendToAllocate(source=Service(), sources=[Account()])


@pytest.mark.unit
def test_spend_to_allocate_get_dependencies_should_collect_source_and_condition_refs():
    block = SpendToAllocate(source=Service(), conditions=[Equals('123', source=Account())])
    deps = [d.get_id() for d in block.get_dependencies()]
    assert deps == ['Service', 'Account']


@pytest.mark.unit
def test_across_elements_to_dict_should_serialize_rules_longhand():
    block = AcrossElements(rules=[GroupRule(name='ec2', condition=Equals('AmazonEC2', source=Service()))])
    assert block.to_dict() == {
        'Rules': [
            {
                'Type': 'Group',
                'Name': 'ec2',
                'Conditions': [{'Equals': 'AmazonEC2', 'Source': 'Service'}],
            }
        ]
    }


@pytest.mark.unit
def test_across_elements_to_dict_should_serialize_groups_shorthand():
    block = AcrossElements(
        source=Service(),
        groups={'compute': [Equals('AmazonEC2', source=Service())]},
    )
    assert block.to_dict() == {
        'Source': 'Service',
        'Groups': {'compute': [{'Equals': 'AmazonEC2', 'Source': 'Service'}]},
    }


@pytest.mark.unit
def test_across_elements_to_dict_should_serialize_group_by_shorthand_without_type_wrapper():
    block = AcrossElements(group_by=GroupByRule(source=Service(), transforms=[Lower()]))
    assert block.to_dict() == {
        'GroupBy': {'Source': 'Service', 'Transforms': [{'Type': 'Lower'}]},
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'kwargs, message',
    [
        pytest.param({}, 'exactly one of rules, groups, or group_by', id='none-specified'),
        pytest.param(
            {'rules': [GroupRule(name='x', condition=Equals('y', source=Service()))], 'groups': {'a': []}},
            'exactly one of rules, groups, or group_by',
            id='two-specified',
        ),
    ],
)
def test_across_elements_should_require_exactly_one_body(kwargs, message):
    with pytest.raises(ValueError, match=message):
        AcrossElements(**kwargs)


@pytest.mark.unit
def test_across_elements_should_raise_when_both_source_and_sources_given():
    with pytest.raises(ValueError, match='Cannot specify both source and sources'):
        AcrossElements(source=Service(), sources=[Account()], rules=[])


@pytest.mark.unit
def test_across_elements_get_dependencies_should_collect_refs_from_each_body_form():
    rules_block = AcrossElements(rules=[GroupRule(name='x', condition=Equals('y', source=Service()))])
    assert [d.get_id() for d in rules_block.get_dependencies()] == ['Service']

    groups_block = AcrossElements(groups={'a': [HasValue(source=Account())]})
    assert [d.get_id() for d in groups_block.get_dependencies()] == ['Account']

    group_by_block = AcrossElements(group_by=GroupByRule(source=Service()))
    assert [d.get_id() for d in group_by_block.get_dependencies()] == ['Service']


@pytest.mark.unit
def test_foreach_element_of_should_behave_as_across_elements():
    block = ForEachElementOf(rules=[GroupRule(name='x', condition=Equals('y', source=Service()))])
    assert isinstance(block, AcrossElements)
    assert block.to_dict() == {'Rules': [{'Type': 'Group', 'Name': 'x', 'Conditions': [{'Equals': 'y', 'Source': 'Service'}]}]}
