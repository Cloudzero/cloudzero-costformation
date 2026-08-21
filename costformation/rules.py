# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Union

from costformation._source_info import _SourceInfoBase, _SourceInfoBlock
from costformation.conditions import Condition
from costformation.transforms import _NORMALIZATION_TRANSLATE, Normalize, Split, Transform

if TYPE_CHECKING:
    from costformation.dimensions import Dimension


def _normalize_metadata_search_value(value: str) -> str:
    """Production CFDL search-value normalization: lowercase + char-translate.

    Mirrors the production CFDL search-value normalization exactly — applies
    only `lower` + the special-char translate (no whitespace strip).
    """
    return value.lower().translate(_NORMALIZATION_TRANSLATE)


class Rule(_SourceInfoBase, ABC):
    """Abstract base class for CFDL rules.

    Concrete subclasses:

    - :class:`GroupRule` — static-name group (``Type: Group``)
    - :class:`GroupByRule` — dynamic-name group (``Type: GroupBy``)
    - :class:`MetadataRule` — substring-matching group (``Type: Metadata``)

    All rules share ``Source`` / ``Sources`` / ``CoalesceSources`` (inherited via
    :class:`_SourceInfoBase`). ``Transforms`` is added by :class:`GroupRule` and
    :class:`GroupByRule` only — Metadata rules do not support Transforms per CFDL.

    **Source resolution.** Rule-level ``source`` / ``sources`` always overrides
    the dimension-level source (CFDL atomic-override semantics). The dimension's
    primary source is supplied as a *fallback* (``dim_source``) and is only used
    when the rule has no source of its own.
    """

    _TYPE: str = ''

    @abstractmethod
    def evaluate(self, data: dict[str, Any], dim_source: 'Dimension | None') -> str | None:
        """Evaluate this rule against ``data``.

        Returns the produced group name on match, otherwise ``None``.
        ``dim_source`` is the dimension-level source used as a fallback when
        the rule has no source and a sourceless condition needs one.
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize this rule to a YAML-ready dictionary."""

    def get_dependencies(self) -> list['Dimension']:
        """Return Dimension instances this rule reads during evaluation.

        Default implementation returns just the source dependencies; subclasses
        extend with condition dependencies.
        """
        return self._source_dependencies()

    def _resolve_source(self, dim_source: 'Dimension | None') -> 'Dimension | None':
        """Rule-level source if set, else the supplied dimension fallback."""
        return self._first_source_dimension() or dim_source


class GroupRule(_SourceInfoBlock, Rule):
    """Static-name group rule (CFDL ``Type: Group``).

    Matches a single condition and produces a fixed group name when it fires.

    Attributes:
        name: Output group name returned when ``condition`` matches.
        condition: The condition that triggers this rule.
        source: Optional single-source override (overrides dimension source for sourceless conditions).
        sources: Optional multi-source override; first source is primary for sourceless conditions.
        coalesce_sources: With ``sources``, emit ``CoalesceSources: True``.
        transforms: Transforms applied to the source value before condition evaluation.
    """

    _TYPE = 'Group'

    def __init__(
        self,
        name: str,
        condition: Condition,
        *,
        source: Optional['Dimension'] = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        transforms: list[Transform] | None = None,
    ):
        self._set_source_info(
            source=source,
            sources=sources,
            coalesce_sources=coalesce_sources,
            transforms=transforms,
        )
        self.name = name
        self.condition = condition

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'Type': self._TYPE}
        if self.name:
            result['Name'] = self.name
        result.update(self._source_info_dict())
        result['Conditions'] = self.condition.to_conditions_list()
        return result

    def evaluate(self, data: dict[str, Any], dim_source: 'Dimension | None') -> str | None:
        """Evaluate this rule against ``data``; return the produced group name on match, else None.

        When the rule has a resolvable source, rule-level transforms are applied to
        that source's value before condition evaluation. The condition is otherwise
        free to resolve its own sources via ``Condition.source`` / ``Condition.sources``.

        When ``self.name`` is non-empty, that's the produced name. When ``self.name`` is
        empty, the rule produces the (possibly transformed) source value as a dynamic
        name — a CFDL convention used to fold "GroupBy with a gating condition" into a
        single Group rule.
        """
        effective_source = self._resolve_source(dim_source)
        evaluation_data = self._apply_transforms(data, effective_source) if effective_source is not None else data
        if not self.condition.evaluate(evaluation_data, effective_source):
            return None
        if self.name:
            return self.name
        if effective_source is None:
            return None
        return evaluation_data.get(effective_source.get_id())

    def get_dependencies(self) -> list['Dimension']:
        return self._source_dependencies() + self.condition.get_dependencies()

    def _apply_transforms(self, data: dict[str, Any], source: 'Dimension') -> dict[str, Any]:
        """Apply rule-level transforms to ``source``'s value in ``data``.

        Mirrors production CFDL: a :class:`Split` whose index lands out of range
        produces ``''``, which production wraps in ``NULLIF(..., '')`` so the
        ref becomes NULL. We model that by storing ``None`` in the returned
        data dict — subsequent conditions reading the source see "missing".
        """
        if not self.transforms:
            return data
        source_id = source.get_id()
        value = data.get(source_id)
        if value is None:
            return data
        for transform in self.transforms:
            value = transform.apply(value)
            if isinstance(transform, Split) and value == '':
                value = None
                break
        return {**data, source_id: value}


class GroupByRule(_SourceInfoBlock, Rule):
    """Dynamic-name group rule (CFDL ``Type: GroupBy``).

    Produces one group per distinct value of the source dimension(s).

    Attributes:
        source: Single dimension or list of dimensions to group by. With a list,
            CFDL emits ``Source: [...]`` for use with ``Format: '{0} - {1}'``.
        sources: Alternative to ``source`` — list of dimensions tried with coalesce logic.
        coalesce_sources: With ``sources``, use the first non-null value.
        transforms: Optional transforms applied to source values.
        conditions: Optional gating conditions; if any is false, the rule produces no group.
        format: Optional format string applied to the produced group name.
    """

    _TYPE = 'GroupBy'

    def __init__(
        self,
        *,
        source: Union['Dimension', list['Dimension']] | None = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        transforms: list[Transform] | None = None,
        conditions: list[Condition] | None = None,
        format: str | None = None,  # noqa: A002  (matches the CFDL YAML key name)
    ):
        if source is None and sources is None:
            raise ValueError('GroupByRule requires either source or sources')
        self._set_source_info(
            source=source,
            sources=sources,
            coalesce_sources=coalesce_sources,
            transforms=transforms,
        )
        self.conditions = conditions or []
        self.format = format

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'Type': self._TYPE}
        result.update(self._source_info_dict())
        if self.conditions:
            result['Conditions'] = [c.to_dict() for c in self.conditions]
        if self.format:
            result['Format'] = self.format
        return result

    def evaluate(self, data: dict[str, Any], dim_source: 'Dimension | None') -> str | None:
        """Evaluate against ``data``; return the (transformed, formatted) value or None.

        **Multi-source non-coalesce** (``sources=[A, B]`` or ``source=[A, B]``,
        ``coalesce_sources=False``): mirrors production's
        ``WHEN HasValue(A) AND HasValue(B) THEN concat(...)`` — every source must
        have a value, transforms apply to each independently, and the format
        (default ``'{0} {1}'``) concatenates them.

        **Coalesce or single source**: production builds a single ref (with
        ``COALESCE`` when ``coalesce_sources=True``); the first non-null value
        is taken, transforms applied, then the format (default ``'{0}'``) emits
        the result.
        """
        gating_source = self._resolve_source(dim_source)
        for condition in self.conditions:
            if not condition.evaluate(data, gating_source):
                return None

        source_dims = self._source_dependencies()
        if not source_dims:
            return None

        if len(source_dims) > 1 and not self.coalesce_sources:
            values: list[str] = []
            for src in source_dims:
                v = data.get(src.get_id())
                if v is None:
                    return None
                v = self._apply_transforms_to_value(v)
                if v is None:
                    return None
                values.append(v)
            format_str = self.format or ' '.join('{' + str(i) + '}' for i in range(len(source_dims)))
            return format_str.format(*values)

        value = self._coalesced_source_value(data)
        if value is None:
            return None
        value = self._apply_transforms_to_value(value)
        if value is None:
            return None
        return self.format.format(value) if self.format else value

    def get_dependencies(self) -> list['Dimension']:
        refs = self._source_dependencies()
        for c in self.conditions:
            refs.extend(c.get_dependencies())
        return refs

    def _coalesced_source_value(self, data: dict[str, Any]) -> Any:
        if self.sources:
            for source_dim in self.sources:
                val = data.get(source_dim.get_id())
                if val is not None:
                    return val
            return None
        primary = self._first_source_dimension()
        return data.get(primary.get_id()) if primary is not None else None

    def _apply_transforms_to_value(self, value: str) -> str | None:
        """Apply ``self.transforms``; return None if a Split produces ``''`` (production NULLIF)."""
        if not self.transforms:
            return value
        for transform in self.transforms:
            value = transform.apply(value)
            if isinstance(transform, Split) and value == '':
                return None
        return value


class MetadataRule(Rule):
    """Substring-matching group rule (CFDL ``Type: Metadata``).

    Searches one or more sources for substring matches against ``values``. Plain
    string entries match as substrings (return the matched substring); dict entries
    map an output name to a list of substrings (any match returns the output name).

    Per CFDL, MetadataRule does **not** support Transforms.

    Attributes:
        source: Single dimension or list of dimensions to search.
        sources: Alternative to ``source`` — list of dimensions emitted as ``Sources:``.
        coalesce_sources: With ``sources``, emit ``CoalesceSources: True``.
        values: Patterns to match — strings or ``{output_name: [substring, ...]}`` dicts.
        format: Optional format string applied to the matched name.
        conditions: Optional gating conditions.
    """

    _TYPE = 'Metadata'

    def __init__(
        self,
        source: Union['Dimension', list['Dimension']] | None = None,
        values: list[str | dict[str, list[str]]] | None = None,
        *,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        format: str | None = None,  # noqa: A002  (matches the CFDL YAML key name)
        conditions: list[Condition] | None = None,
    ):
        if values is None:
            raise ValueError('MetadataRule requires values')
        if source is None and sources is None:
            raise ValueError('MetadataRule requires either source or sources')
        self._set_source_info(
            source=source,
            sources=sources,
            coalesce_sources=coalesce_sources,
        )
        self.values = values
        self.format = format
        self.conditions = conditions or []

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'Type': self._TYPE}
        result.update(self._source_info_dict())
        if self.format:
            result['Format'] = self.format
        result['Values'] = self.values
        if self.conditions:
            result['Conditions'] = [c.to_dict() for c in self.conditions]
        return result

    def evaluate(self, data: dict[str, Any], dim_source: 'Dimension | None') -> str | None:
        """Evaluate against ``data``; return the matched (or formatted) name or None.

        Iterates **patterns first** (matching production, which unrolls a Metadata
        rule into one Group rule per ``value_group`` in CASE order). For each
        pattern, the implicit ``Contains`` is OR'd across all sources that have
        a value — this mirrors the production source-split-by-OR behavior.
        """
        gating_source = self._resolve_source(dim_source)
        for condition in self.conditions:
            if not condition.evaluate(data, gating_source):
                return None

        normalized_sources = [
            Normalize().apply(v)
            for source_dim in self._source_dependencies()
            if (v := data.get(source_dim.get_id())) is not None
        ]
        if not normalized_sources:
            return None

        for value_pattern in self.values:
            output = self._match_pattern_against_sources(value_pattern, normalized_sources)
            if output is not None:
                return self.format.format(output) if self.format else output

        return None

    def get_dependencies(self) -> list['Dimension']:
        refs = self._source_dependencies()
        for c in self.conditions:
            refs.extend(c.get_dependencies())
        return refs

    @staticmethod
    def _match_pattern_against_sources(
        value_pattern: 'str | dict[str, list[str]]', normalized_sources: list[str]
    ) -> str | None:
        """Return the unformatted output name if any source contains the pattern's terms."""
        if isinstance(value_pattern, str):
            term = _normalize_metadata_search_value(value_pattern)
            if any(term in src for src in normalized_sources):
                return value_pattern.strip('-')
            return None
        for output_name, match_list in value_pattern.items():
            terms = [_normalize_metadata_search_value(output_name)] + [_normalize_metadata_search_value(m) for m in match_list]
            if any(term in src for src in normalized_sources for term in terms):
                return output_name.strip('-')
        return None
