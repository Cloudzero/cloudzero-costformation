# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation import core_dimensions as cd


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_id',
    [
        pytest.param(cd.Account, 'Account', id='account'),
        pytest.param(cd.Service, 'Service', id='service'),
        pytest.param(cd.Region, 'Region', id='region'),
        pytest.param(cd.UsageDay, 'UsageDay', id='usage-day'),
        pytest.param(cd.CloudProvider, 'CloudProvider', id='cloud-provider'),
    ],
)
def test_simple_core_dimensions_should_use_class_name_as_id(dimension_cls, expected_id):
    assert dimension_cls().get_id() == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    'dimension_cls, expected_id',
    [
        pytest.param(cd.K8s_Cluster, 'K8s:Cluster', id='k8s-cluster'),
        pytest.param(cd.K8s_Namespace, 'K8s:Namespace', id='k8s-namespace'),
        pytest.param(cd.K8s_Workload, 'K8s:Workload', id='k8s-workload'),
    ],
)
def test_underscore_core_dimensions_should_convert_to_colons(dimension_cls, expected_id):
    assert dimension_cls().get_id() == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    'tag_key, expected_id',
    [
        pytest.param('Environment', 'Tag:Environment', id='simple-tag'),
        pytest.param('application', 'Tag:application', id='lowercase-tag'),
        pytest.param('aws:cloudformation:stack-name', 'Tag:aws:cloudformation:stack-name', id='tag-with-colons'),
    ],
)
def test_tag_should_embed_key_in_id(tag_key, expected_id):
    assert cd.Tag(tag_key).get_id() == expected_id


@pytest.mark.unit
@pytest.mark.parametrize(
    'label_name, expected_id',
    [
        pytest.param('app', 'K8s:Label:app', id='simple-label'),
        pytest.param('node:instance-type', 'K8s:Label:node:instance-type', id='label-with-colons'),
    ],
)
def test_k8s_label_should_embed_name_in_id(label_name, expected_id):
    assert cd.K8s_Label(label_name).get_id() == expected_id


@pytest.mark.unit
def test_core_dimension_get_reference_should_equal_id():
    service = cd.Service()
    assert service.get_reference() == service.get_id()


@pytest.mark.unit
def test_core_dimension_to_dict_should_raise_type_error():
    with pytest.raises(TypeError, match='cannot be serialized'):
        cd.Service().to_dict()
