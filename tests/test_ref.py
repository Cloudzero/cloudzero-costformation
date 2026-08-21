# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation.ref import Ref


@pytest.mark.unit
@pytest.mark.parametrize(
    'reference_id',
    [
        pytest.param('User:Defined:Customer', id='user-defined'),
        pytest.param('CZ:Defined:ServiceDisplay', id='cz-defined'),
        pytest.param('Service', id='core-dimension'),
        pytest.param('Tag:Environment', id='tag-with-key'),
    ],
)
def test_ref_get_id_should_return_reference_id(reference_id):
    assert Ref(reference_id).get_id() == reference_id


@pytest.mark.unit
def test_ref_get_reference_should_return_reference_id():
    assert Ref('User:Defined:Customer').get_reference() == 'User:Defined:Customer'


@pytest.mark.unit
def test_ref_to_dict_should_raise_type_error():
    with pytest.raises(TypeError, match='cannot be serialized'):
        Ref('User:Defined:Customer').to_dict()
