# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
from abc import ABC, abstractmethod
from typing import Any

# Production CFDL special-character set — each char in the
# "from" string is translated to '-'. Mirrors the production CFDL
# normalization character set exactly. NOTE: characters not in this set (e.g. '@', '?',
# '+', '|') are *preserved* — production CFDL does not regex-substitute all
# non-alphanumeric runs, only this specific set.
NORMALIZATION_CHARS_FROM = " .,/#!$%^&*;:=_`~()'"
_NORMALIZATION_TRANSLATE = str.maketrans(NORMALIZATION_CHARS_FROM, '-' * len(NORMALIZATION_CHARS_FROM))


class Transform(ABC):
    """Base class for value transforms"""

    @abstractmethod
    def apply(self, value: str) -> str:
        """Apply transform to a value"""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert transform to YAML-ready dictionary"""


class Lower(Transform):
    """Convert value to lowercase"""

    def apply(self, value: str) -> str:
        return value.lower()

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Lower'}


class Upper(Transform):
    """Convert value to uppercase"""

    def apply(self, value: str) -> str:
        return value.upper()

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Upper'}


class Split(Transform):
    """Split value by delimiter and extract element at index.

    Mirrors production CFDL's Snowflake-backed ``SPLIT_PART`` semantics:

    - **1-based indexing**: ``index=1`` is the first field, ``index=2`` the second, etc.
    - ``index=0`` is treated as ``index=1`` (Snowflake compatibility).
    - **Negative indexes count from the end**: ``index=-1`` is the last field.
    - **Out of range returns ``''``** — which downstream rules treat as no-value
      (matching production's ``NULLIF(SPLIT_PART(...), '')`` wrapper).

    Attributes:
        delimiter: String to split on
        index: 1-based index of element to extract after splitting
        maxsplit: Optional maximum number of splits to perform
    """

    def __init__(self, delimiter: str, index: int, maxsplit: int | None = None):
        self.delimiter = delimiter
        self.index = index
        self.maxsplit = maxsplit

    def apply(self, value: str) -> str:
        if self.maxsplit is not None:
            parts = value.split(self.delimiter, self.maxsplit)
        else:
            parts = value.split(self.delimiter)

        if self.index == 0:
            return parts[0]
        if self.index > 0:
            return parts[self.index - 1] if self.index <= len(parts) else ''
        return parts[self.index] if -self.index <= len(parts) else ''

    def to_dict(self) -> dict[str, Any]:
        result = {'Type': 'Split', 'Delimiter': self.delimiter, 'Index': self.index}
        if self.maxsplit is not None:
            result['Maxsplit'] = self.maxsplit
        return result


class Title(Transform):
    """Convert value to title case"""

    def apply(self, value: str) -> str:
        return value.title()

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Title'}


# Production CFDL Trim is Snowflake ``TRIM(input, ' \t')`` — strips ONLY space
# and tab at the boundaries, not all whitespace. Mirror that here so newlines /
# vertical tab / form feed / carriage return at edges are preserved.
_TRIM_CHARS = ' \t'


class Trim(Transform):
    """Remove leading and trailing space and tab characters.

    Mirrors production ``TRIM(input, ' \\t')``. Other whitespace (newline,
    carriage return, form feed, vertical tab) at the boundary is preserved.
    """

    def apply(self, value: str) -> str:
        return value.strip(_TRIM_CHARS)

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Trim'}


class Clean(Transform):
    """Translate the CFDL special-char set to ``-`` and trim space/tab.

    Mirrors production CFDL ``Clean``: special-char translation, then trim.
    Characters NOT in :data:`NORMALIZATION_CHARS_FROM` are preserved verbatim.
    """

    def apply(self, value: str) -> str:
        return value.translate(_NORMALIZATION_TRANSLATE).strip(_TRIM_CHARS)

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Clean'}


class Normalize(Transform):
    """Translate special chars to ``-``, lowercase, trim space/tab.

    Mirrors production CFDL ``Normalize``: special-char translation,
    then lowercase, then trim. Characters NOT in
    :data:`NORMALIZATION_CHARS_FROM` are preserved verbatim. Leading and
    trailing dashes (created by edge-of-string special chars) are *not*
    stripped — only space and tab are stripped at the boundary.
    """

    def apply(self, value: str) -> str:
        return value.translate(_NORMALIZATION_TRANSLATE).lower().strip(_TRIM_CHARS)

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Normalize'}


class Lookup(Transform):
    """Resolve a value from a named key within a serialized dictionary.

    Mirrors production CFDL ``{'Type': 'Lookup', 'Key': <key>}``. :meth:`apply`
    treats the incoming value as a JSON object and returns the string stored
    under :attr:`key`. When the value is not a JSON object, the key is absent,
    or its value is not a string, ``''`` is returned — matching how the other
    transforms model no-value (production CFDL wraps it in ``NULLIF``).

    Attributes:
        key: The key to resolve from the deserialized value.
    """

    def __init__(self, key: str):
        self.key = key

    def apply(self, value: str) -> str:
        try:
            data = json.loads(value)
        except (json.JSONDecodeError, TypeError, RecursionError):
            return ''
        if isinstance(data, dict):
            resolved = data.get(self.key)
            return resolved if isinstance(resolved, str) else ''
        return ''

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Lookup', 'Key': self.key}
