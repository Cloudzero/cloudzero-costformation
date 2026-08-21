# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared CFDL source-info mixins.

Two layered mixins matching the CFDL ``SOURCE_INFORMATION_SCHEMA`` shape:

- :class:`_SourceInfoBase` provides ``Source`` / ``Sources`` / ``CoalesceSources``.
- :class:`_SourceInfoBlock` extends the base with ``Transforms``.

Constructs that support transforms (GroupDimension, SpendToAllocate, AcrossElements,
GroupRule, GroupByRule) inherit from :class:`_SourceInfoBlock`. Constructs that
don't (MetadataRule, per the CFDL spec) inherit from :class:`_SourceInfoBase`.

Both mixins declare class-level attribute defaults and supply ``_set_source_info``
plus serialization / dependency helpers, but deliberately have no ``__init__`` so
that classes which rely on the class-attribute subclass pattern (e.g.,
GroupDimension) are unaffected when they inherit.
"""

from typing import TYPE_CHECKING, Any, Union

from costformation.transforms import Transform

if TYPE_CHECKING:
    from costformation.dimensions import Dimension


class _SourceInfoBase:
    """``Source`` / ``Sources`` / ``CoalesceSources`` block (no ``Transforms``)."""

    source: Union['Dimension', list['Dimension']] | None = None
    sources: list['Dimension'] | None = None
    coalesce_sources: bool = False

    def _set_source_info(
        self,
        *,
        source: Union['Dimension', list['Dimension']] | None = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
    ) -> None:
        """Initialize source/sources/coalesce_sources with the standard XOR check."""
        if source is not None and sources is not None:
            raise ValueError('Cannot specify both source and sources')
        self.source = source
        self.sources = sources
        self.coalesce_sources = coalesce_sources

    def _source_info_dict(self) -> dict[str, Any]:
        """Serialize Source / Sources / CoalesceSources keys."""
        result: dict[str, Any] = {}
        if self.sources is not None:
            result['Sources'] = [s.get_reference() for s in self.sources]
            if self.coalesce_sources:
                result['CoalesceSources'] = True
        elif self.source is not None:
            if isinstance(self.source, list):
                result['Source'] = [s.get_reference() for s in self.source]
            else:
                result['Source'] = self.source.get_reference()
        return result

    def _source_dependencies(self) -> list['Dimension']:
        """Dimensions referenced via ``source`` or ``sources``."""
        refs: list[Dimension] = []
        if self.sources is not None:
            refs.extend(self.sources)
        elif self.source is not None:
            if isinstance(self.source, list):
                refs.extend(self.source)
            else:
                refs.append(self.source)
        return refs

    def _first_source_dimension(self) -> 'Dimension | None':
        """First Dimension referenced via ``source`` / ``sources``, or None."""
        deps = self._source_dependencies()
        return deps[0] if deps else None


class _SourceInfoBlock(_SourceInfoBase):
    """Full ``SOURCE_INFORMATION_SCHEMA``: base block plus ``Transforms``."""

    transforms: list[Transform] = []

    def _set_source_info(
        self,
        *,
        source: Union['Dimension', list['Dimension']] | None = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        transforms: list[Transform] | None = None,
    ) -> None:
        super()._set_source_info(source=source, sources=sources, coalesce_sources=coalesce_sources)
        self.transforms = transforms or []

    def _source_info_dict(self) -> dict[str, Any]:
        result = super()._source_info_dict()
        if self.transforms:
            result['Transforms'] = [t.to_dict() for t in self.transforms]
        return result
