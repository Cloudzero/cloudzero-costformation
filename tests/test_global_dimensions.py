# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation import global_dimensions as gd


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_id',
    [
        pytest.param(gd.ServiceDisplay, 'ServiceDisplay', id='service-display'),
        pytest.param(gd.Category, 'Category', id='category'),
        pytest.param(gd.ResourceType, 'ResourceType', id='resource-type'),
        pytest.param(gd.BillingLineItem, 'BillingLineItem', id='billing-line-item'),
    ],
)
def test_global_dimensions_should_use_class_name_as_id(dimension_cls, expected_id):
    assert dimension_cls().get_id() == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_id',
    [
        pytest.param(gd.GenAI_Model, 'GenAI_Model', id='genai-model'),
        pytest.param(gd.ServiceDetail_Breakdown_AWS, 'ServiceDetail_Breakdown_AWS', id='service-detail-breakdown-aws'),
        pytest.param(gd.NetworkingCategory_VPCFlowlog, 'NetworkingCategory_VPCFlowlog', id='networking-category-vpcflowlog'),
    ],
)
def test_global_dimensions_with_underscores_should_preserve_underscores_in_id(dimension_cls, expected_id):
    assert dimension_cls().get_id() == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_reference',
    [
        pytest.param(gd.ServiceDisplay, 'CZ:Defined:ServiceDisplay', id='service-display'),
        pytest.param(gd.Category, 'CZ:Defined:Category', id='category'),
        pytest.param(gd.ResourceType, 'CZ:Defined:ResourceType', id='resource-type'),
        pytest.param(gd.NetworkingSubCategory, 'CZ:Defined:NetworkingSubCategory', id='networking-sub-category'),
    ],
)
def test_global_dimensions_should_prefix_reference_with_cz_defined(dimension_cls, expected_reference):
    assert dimension_cls().get_reference() == expected_reference


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_reference',
    [
        pytest.param(gd.GenAI_Model, 'CZ:Defined:GenAI_Model', id='genai-model'),
        pytest.param(
            gd.ServiceDetail_Breakdown_AWS, 'CZ:Defined:ServiceDetail_Breakdown_AWS', id='service-detail-breakdown-aws'
        ),
        pytest.param(
            gd.NetworkingCategory_VPCFlowlog, 'CZ:Defined:NetworkingCategory_VPCFlowlog', id='networking-category-vpcflowlog'
        ),
    ],
)
def test_global_dimensions_with_underscores_should_not_convert_underscores_in_reference(dimension_cls, expected_reference):
    assert dimension_cls().get_reference() == expected_reference


@pytest.mark.unit
def test_global_dimension_to_dict_should_raise_type_error():
    with pytest.raises(TypeError, match='cannot be serialized'):
        gd.ServiceDisplay().to_dict()
