# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Reference dimension for testing purposes.

Ref() allows creating placeholder dimensions that don't actually exist in the file.
This is useful for testing individual dimensions in isolation without defining all dependencies.

Usage:
    from costformation import Ref

    # Reference a dimension that isn't defined
    class MyDimension(GroupDimension):
        source = Ref('User:Defined:SomeOtherDimension')
        rules = [...]
"""

from typing import Any

from costformation.dimensions import Dimension


class Ref(Dimension):
    """Reference to a dimension by its fully-qualified ID

    Used for testing purposes to reference dimensions without defining them.
    The reference ID is inserted verbatim into the generated YAML.

    Args:
        reference_id: Fully-qualified dimension ID (e.g., 'User:Defined:MyDim', 'Service', 'CZ:Defined:Category')

    Usage:
        Ref('User:Defined:Customer')
        Ref('CZ:Defined:ServiceDisplay')
        Ref('Tag:Environment')
    """

    def __init__(self, reference_id: str):
        self.reference_id = reference_id

    def get_id(self) -> str:
        """Return the reference ID directly"""
        return self.reference_id

    def get_reference(self) -> str:
        """Return the reference ID directly"""
        return self.reference_id

    def to_dict(self) -> dict[str, Any]:
        """References cannot be serialized"""
        raise TypeError(
            f'Ref({self.reference_id}) cannot be serialized to YAML. '
            f'Ref is only for testing and should only be used as a source/reference in other dimensions.'
        )
