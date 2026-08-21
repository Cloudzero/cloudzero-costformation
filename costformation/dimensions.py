# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from functools import cache
from typing import Any, Union, cast

import yaml

from costformation._source_info import _SourceInfoBlock
from costformation.allocations import (
    AllocationMethod,
    ElementCutoff,
    FixedRate,
    ProportionalMethod,
)
from costformation.conditions import (
    After,
    AfterOrEquals,
    Before,
    BeforeOrEquals,
    BeginsWith,
    Condition,
    Contains,
    EndsWith,
    Equals,
    HasValue,
    Matches,
)
from costformation.rules import GroupByRule, Rule
from costformation.transforms import Transform

# Production CFDL maps these dimension IDs to the same underlying partition column
# (both ``product_family`` and ``usage_family`` resolve to the same partition). Mirror that
# during ``evaluate`` — if a caller provides one, treat it as having provided both.
_ALIAS_GROUPS: list[frozenset[str]] = [frozenset({'UsageFamily', 'ProductFamily'})]


def _expand_alias_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Carry the same value across every alias in a group when at least one is present.

    If the caller supplies multiple keys from the same group with different values
    (which would be inconsistent vs. production), the value of whichever key was
    inserted into ``data`` first wins; the alias keys are not overwritten.
    """
    expanded = data
    for group in _ALIAS_GROUPS:
        present = next((k for k in expanded if k in group), None)
        if present is None:
            continue
        value = expanded[present]
        missing = group - expanded.keys()
        if missing:
            expanded = {**expanded, **dict.fromkeys(missing, value)}
    return expanded


class Dimension(ABC):
    """Base class for all dimensions"""

    name: str | None = None  # Optional display name (defaults to class name)
    hide: bool | None = None  # Whether to hide dimension from UI
    disable: bool | None = None  # Whether to disable dimension from processing

    def equals(self, value: Union[str, list[str]]) -> Equals:
        return Equals(value, source=self)

    def contains(self, value: Union[str, list[str]]) -> Contains:
        return Contains(value, source=self)

    def begins_with(self, value: Union[str, list[str]]) -> BeginsWith:
        return BeginsWith(value, source=self)

    def ends_with(self, value: Union[str, list[str]]) -> EndsWith:
        return EndsWith(value, source=self)

    def matches(self, pattern: str) -> Matches:
        return Matches(pattern, source=self)

    def has_value(self, value: bool = True) -> HasValue:
        return HasValue(value, source=self)

    def before(self, value: str) -> Before:
        return Before(value, source=self)

    def before_or_equals(self, value: str) -> BeforeOrEquals:
        return BeforeOrEquals(value, source=self)

    def after(self, value: str) -> After:
        return After(value, source=self)

    def after_or_equals(self, value: str) -> AfterOrEquals:
        return AfterOrEquals(value, source=self)

    def get_id(self) -> str:
        """Get dimension ID (class name)"""
        return self.__class__.__name__

    def get_name(self) -> str:
        """Get display name (defaults to ID if not set)"""
        return self.name if self.name else self.get_id()

    @abstractmethod
    def get_reference(self) -> str:
        """Get YAML reference string for this dimension"""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert dimension to YAML-ready dictionary"""

    def get_dependencies(self) -> list['Dimension']:
        """Return Dimension instances this one reads during evaluation."""
        return []

    @classmethod
    def evaluate(cls, data: dict[str, Any]) -> str | None:
        """Compute this dimension's value from ``data``. Overridden by GroupDimension
        (matches rules) and AllocationDimension (raises — allocations aren't evaluable)."""
        raise NotImplementedError(
            f'{cls.__name__}.evaluate is not implemented; only GroupDimension subclasses evaluate to a value.'
        )


class ReferenceOnlyDimension(Dimension):
    """Dimensions that are never defined in CostFormation YAML, only referenced.

    These dimensions exist outside the user's CostFormation file (cloud provider
    primitives, CloudZero-managed dimensions) and can only be referenced from it.
    Attempting to serialize one is an error.
    """

    def to_dict(self) -> dict[str, Any]:
        raise TypeError(
            f'{self.get_id()} cannot be serialized to YAML. '
            f'Reference-only dimensions are never defined, only referenced in CostFormation files.'
        )


class CoreDimension(ReferenceOnlyDimension):
    """Core dimensions - cloud provider primitives that are never defined in CostFormation YAML

    Core dimensions exist at the root level and can only be referenced, never defined.
    They represent fundamental cloud provider billing dimensions like Account, Service, Region, etc.

    Class names with underscores are converted to colons (e.g., K8s_Cluster -> K8s:Cluster).
    """

    def get_id(self) -> str:
        """Get dimension ID (class name with underscores replaced by colons)"""
        return super().get_id().replace('_', ':')

    def get_reference(self) -> str:
        return self.get_id()


class GlobalDimension(ReferenceOnlyDimension):
    """Global dimensions - CloudZero-managed dimensions with CZ:Defined: prefix

    Global dimensions provide additional cloud provider insights and are managed by CloudZero.
    Like core dimensions, they are never defined in CostFormation YAML, only referenced.

    Underscores in the class name are preserved in the ID
    (e.g., GenAI_Model -> GenAI_Model, referenced as CZ:Defined:GenAI_Model).
    """

    def get_reference(self) -> str:
        return f'CZ:Defined:{self.get_id()}'


class GroupDimension(Dimension, _SourceInfoBlock):
    """User-defined group dimension with source(s) and rules.

    Inherits ``source`` / ``sources`` / ``coalesce_sources`` / ``transforms`` from
    ``_SourceInfoBlock``; see that class for their semantics.

    Additional attributes:
        rules: List of rules (any :class:`Rule` subclass) for grouping
        default_value: Default value when no rules match
        child: Child dimension for hierarchical relationships
        override: Dimension whose values this one overrides
    """

    id: str | None = (
        None  # Optional explicit dimension ID; defaults to the class name. Use when the desired ID isn't a valid Python identifier (e.g. a hyphenated `cost-center`).
    )
    rules: list[Rule] = []
    default_value: str | None = None
    child: Dimension | None = None
    override: Dimension | None = None

    def get_id(self) -> str:
        return self.id if self.id is not None else super().get_id()

    def get_reference(self) -> str:
        return f'User:Defined:{self.get_id()}'

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        # Add Name only if explicitly set (not default to class name)
        if self.name is not None:
            result['Name'] = self.get_name()

        # Source / Sources / CoalesceSources / Transforms (from _SourceInfoBlock)
        result.update(self._source_info_dict())

        # Add rules
        result['Rules'] = [rule.to_dict() for rule in self.rules]

        if self.default_value is not None:
            result['DefaultValue'] = self.default_value

        if self.child is not None:
            result['Child'] = self.child.get_reference()

        if self.override is not None:
            result['Override'] = self.override.get_reference()

        if self.hide is not None:
            result['Hide'] = self.hide

        if self.disable is not None:
            result['Disable'] = self.disable

        return result

    @classmethod
    def evaluate(cls, data: dict[str, Any]) -> str | None:
        """Evaluate ``data`` against this dimension's rules in order.

        Returns the first matching rule's group name, otherwise ``default_value``
        (or ``None`` if unset). Dimension-level transforms are applied to the
        primary source's value before rules see the data; rules then apply their
        own source resolution and (for ``GroupRule`` / ``GroupByRule``) any
        rule-level transforms.
        """
        instance = cls()
        evaluation_data = instance._apply_dim_transforms(_expand_alias_keys(data))
        # When the dim has a list-valued source/sources, sourceless gating conditions
        # in rules must OR across all of them (CFDL multi-source semantics). Iterate
        # each dim source as the fallback per rule. A dim with no source falls back
        # to a single ``None`` so rules with sourced conditions still run.
        dim_sources: list[Dimension | None] = list(instance._source_dependencies()) or [None]
        for rule in cls.rules:
            for src in dim_sources:
                result = rule.evaluate(evaluation_data, src)
                if result is not None:
                    return result
        return instance.default_value

    def _apply_dim_transforms(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply dimension-level transforms to every source value in ``data``.

        When the dim has a list-valued ``source=[a, b]`` (or ``sources=[…]``),
        transforms apply to each source's value independently — matching
        production CFDL, which lowers/normalizes each source before rules see it.
        """
        if not self.transforms:
            return data
        result = data
        for source in self._source_dependencies():
            source_id = source.get_id()
            value = result.get(source_id)
            if value is None:
                continue
            for transform in self.transforms:
                value = transform.apply(value)
            result = {**result, source_id: value}
        return result

    def get_dependencies(self) -> list[Dimension]:
        refs = self._source_dependencies()
        for rule in self.rules:
            refs.extend(rule.get_dependencies())
        return refs


class SpendToAllocate(_SourceInfoBlock):
    """Selects the pool of spend to allocate inside an ``AllocateByRules`` dimension.

    Extends the shared ``_SourceInfoBlock`` (source / sources / coalesce_sources /
    transforms) with a ``conditions`` list that narrows the spend.
    """

    def __init__(
        self,
        *,
        source: Union['Dimension', list['Dimension']] | None = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        transforms: list[Transform] | None = None,
        conditions: list[Condition] | None = None,
    ):
        self._set_source_info(
            source=source,
            sources=sources,
            coalesce_sources=coalesce_sources,
            transforms=transforms,
        )
        self.conditions = conditions or []

    def to_dict(self) -> dict[str, Any]:
        result = self._source_info_dict()
        if self.conditions:
            result['Conditions'] = [c.to_dict() for c in self.conditions]
        return result

    def get_dependencies(self) -> list[Dimension]:
        refs = self._source_dependencies()
        for c in self.conditions:
            refs.extend(c.get_dependencies())
        return refs


class AcrossElements(_SourceInfoBlock):
    """Selects the dimension elements that the allocated spend is distributed across.

    Extends ``_SourceInfoBlock`` and additionally requires **exactly one** of the
    three body forms defined by CFDL: ``rules`` (longhand ``Rules``), ``groups``
    (shorthand ``Groups`` mapping), or ``group_by`` (shorthand ``GroupBy`` rule).
    """

    def __init__(
        self,
        *,
        source: Union['Dimension', list['Dimension']] | None = None,
        sources: list['Dimension'] | None = None,
        coalesce_sources: bool = False,
        transforms: list[Transform] | None = None,
        rules: list[Rule] | None = None,
        groups: dict[str, list[Condition]] | None = None,
        group_by: GroupByRule | None = None,
    ):
        specified = [x is not None for x in (rules, groups, group_by)]
        if sum(specified) != 1:
            raise ValueError(f'{type(self).__name__} requires exactly one of rules, groups, or group_by')
        self._set_source_info(
            source=source,
            sources=sources,
            coalesce_sources=coalesce_sources,
            transforms=transforms,
        )
        self.rules = rules
        self.groups = groups
        self.group_by = group_by

    def to_dict(self) -> dict[str, Any]:
        result = self._source_info_dict()
        if self.rules is not None:
            result['Rules'] = [r.to_dict() for r in self.rules]
        elif self.groups is not None:
            result['Groups'] = {name: [c.to_dict() for c in conds] for name, conds in self.groups.items()}
        elif self.group_by is not None:
            # GroupByRule.to_dict emits a 'Type: GroupBy' wrapper; in this context
            # the body is inlined under the 'GroupBy:' key, so strip the Type.
            body = self.group_by.to_dict()
            result['GroupBy'] = {k: v for k, v in body.items() if k != 'Type'}
        return result

    def get_dependencies(self) -> list[Dimension]:
        refs = self._source_dependencies()
        if self.rules is not None:
            for r in self.rules:
                refs.extend(r.get_dependencies())
        elif self.groups is not None:
            for conds in self.groups.values():
                for c in conds:
                    refs.extend(c.get_dependencies())
        elif self.group_by is not None:
            refs.extend(self.group_by.get_dependencies())
        return refs


class ForEachElementOf(AcrossElements):
    """Second-level partition for Proportional allocation.

    Schema-identical to :class:`AcrossElements` — the same ``source`` / ``sources``
    / ``coalesce_sources`` / ``transforms`` plus one of ``rules`` / ``groups`` /
    ``group_by``.
    """


class AllocationDimension(Dimension):
    """Allocation dimension: telemetry-stream or rule-based distribution of spend.

    Use one form per dimension. Both forms accept ``element_cutoff`` to bucket
    small elements.

    Telemetry (AllocateByStreams):
        streams: List of telemetry stream names.
        rate: Optional :class:`FixedRate` for rate-based allocation.
              Forbidden with ``element_cutoff``.

    Rule-based (AllocateByRules):
        allocation_method: :class:`AllocationMethod` enum (simple form) or
                           :class:`ProportionalMethod` (advanced Proportional spec).
        spend_to_allocate: :class:`SpendToAllocate`, or a ``list[Condition]``
                           shorthand (equivalent to
                           ``SpendToAllocate(conditions=[...])``). Required when
                           allocation_method is set.
        across_elements: :class:`AcrossElements`, or a ``list[Rule]`` shorthand
                         (equivalent to ``AcrossElements(rules=[...])``). Required
                         when allocation_method is set.
        foreach_element_of: Optional :class:`ForEachElementOf`; requires
                            Proportional allocation.

    Common:
        element_cutoff: Optional :class:`ElementCutoff`. Forbidden with rate-based
                        streams and with Even allocation method.
    """

    id: str | None = (
        None  # Optional explicit dimension ID; defaults to the class name. Use when the desired ID isn't a valid Python identifier (e.g. a hyphenated `cost-center`).
    )

    # AllocateByStreams
    streams: list[str] = []
    rate: FixedRate | None = None

    # AllocateByRules
    allocation_method: Union[AllocationMethod, ProportionalMethod, None] = None
    spend_to_allocate: Union[SpendToAllocate, list[Condition], None] = None
    across_elements: Union[AcrossElements, list[Rule], None] = None
    foreach_element_of: ForEachElementOf | None = None

    # Both forms
    element_cutoff: ElementCutoff | None = None

    def get_id(self) -> str:
        return self.id if self.id is not None else super().get_id()

    def get_reference(self) -> str:
        return f'User:Defined:{self.get_id()}'

    def to_dict(self) -> dict[str, Any]:
        self._validate()
        result: dict[str, Any] = {'Type': 'Allocation'}

        if self.name is not None:
            result['Name'] = self.get_name()
        if self.hide is not None:
            result['Hide'] = self.hide

        if self.streams:
            streams_block: dict[str, Any] = {'Streams': self.streams}
            if self.rate is not None:
                streams_block['Rate'] = self.rate.to_dict()
            result['AllocateByStreams'] = streams_block
        elif self.allocation_method is not None:
            result['AllocateByRules'] = self._allocate_by_rules_dict()

        if self.element_cutoff is not None:
            result['ElementCutoff'] = self.element_cutoff.to_dict()

        if self.disable is not None:
            result['Disable'] = self.disable

        return result

    def _validate(self) -> None:
        """Cross-field validation that can't be enforced by types alone."""
        has_streams = bool(self.streams)
        has_rules = self.allocation_method is not None

        if has_streams and has_rules:
            raise ValueError(
                f'{type(self).__name__}: cannot combine AllocateByStreams (streams) with AllocateByRules (allocation_method)'
            )

        if has_rules:
            if self.spend_to_allocate is None:
                raise ValueError(f'{type(self).__name__}: allocation_method requires spend_to_allocate')
            if self.across_elements is None:
                raise ValueError(f'{type(self).__name__}: allocation_method requires across_elements')

        if self.element_cutoff is not None:
            if self.rate is not None:
                raise ValueError(f'{type(self).__name__}: element_cutoff is not supported with rate-based AllocateByStreams')
            if self.allocation_method == AllocationMethod.EVEN:
                raise ValueError(f'{type(self).__name__}: element_cutoff is not supported with Even allocation method')

        if self.foreach_element_of is not None:
            method = self.allocation_method
            is_proportional = method == AllocationMethod.PROPORTIONAL or isinstance(method, ProportionalMethod)
            if not is_proportional:
                raise ValueError(f'{type(self).__name__}: foreach_element_of requires Proportional allocation_method')

    def _allocate_by_rules_dict(self) -> dict[str, Any]:
        method = self.allocation_method
        method_dict: Union[str, dict[str, Any]]
        if isinstance(method, AllocationMethod):
            method_dict = method.value
        elif isinstance(method, ProportionalMethod):
            method_dict = method.to_dict()
        else:
            raise ValueError(f'{type(self).__name__}: allocation_method must be set')

        spend = self.spend_to_allocate
        if spend is None:
            raise ValueError(f'{type(self).__name__}: spend_to_allocate must be set')
        if isinstance(spend, list):
            spend = SpendToAllocate(conditions=spend)

        across = self.across_elements
        if across is None:
            raise ValueError(f'{type(self).__name__}: across_elements must be set')
        if isinstance(across, list):
            across = AcrossElements(rules=across)

        block: dict[str, Any] = {
            'AllocationMethod': method_dict,
            'SpendToAllocate': spend.to_dict(),
            'AcrossElements': across.to_dict(),
        }
        if self.foreach_element_of is not None:
            block['ForEachElementOf'] = self.foreach_element_of.to_dict()
        return block

    @classmethod
    def evaluate(cls, data: dict[str, Any]) -> str | None:
        raise TypeError(
            f'Allocation dimension {cls.__name__} cannot be evaluated. '
            f'Allocation dimensions describe how spend is distributed by the billing system, '
            f'not a value to compute.'
        )


class CostFormation:
    """Top-level CostFormation object that holds a collection of dimensions"""

    def __init__(self, dimensions: list[Dimension]):
        self.dimensions = dimensions

    def to_dict(self) -> dict[str, Any]:
        return {
            'Dimensions': {dim.get_id(): dim.to_dict() for dim in self.dimensions},
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def evaluate(
        self,
        inputs: dict[str, Any],
        output_dimension_id: str,
        allow_missing_inputs: bool = False,
    ) -> str | None:
        """Evaluate ``output_dimension_id`` against ``inputs``, transitively resolving
        any other dimensions in this CostFormation that it depends on.

        Any value supplied in ``inputs`` is used as-is and short-circuits evaluation —
        this works for both external dimensions (Tag, Service, ...) and dimensions
        defined in this CostFormation, allowing overrides for testing or when an
        upstream value has been precomputed.

        If a referenced dimension is neither in ``inputs`` nor defined in this
        CostFormation, ``ValueError`` is raised. Set ``allow_missing_inputs=True``
        to treat missing inputs as ``None`` instead.
        """
        inputs = _expand_alias_keys(inputs)
        by_id = {dim.get_id(): dim for dim in self.dimensions}
        if output_dimension_id not in by_id:
            raise ValueError(f"Dimension '{output_dimension_id}' is not in this CostFormation")

        visiting: set[str] = set()

        @cache
        def resolve(dim_id: str) -> str | None:
            if dim_id in inputs:
                return cast('str | None', inputs[dim_id])
            if dim_id not in by_id:
                if not allow_missing_inputs:
                    raise ValueError(f"Required input '{dim_id}' was not provided")
                return None
            if dim_id in visiting:
                raise ValueError(f"Cycle detected in CostFormation involving '{dim_id}'")
            dim = by_id[dim_id]
            # Allocation dimensions can't be computed — they describe how the
            # billing system distributes spend, not a value. Under
            # ``allow_missing_inputs=True`` treat them as ``None`` so transitive
            # evaluation chains don't blow up.
            if isinstance(dim, AllocationDimension):
                if not allow_missing_inputs:
                    raise ValueError(
                        f"Allocation dimension '{dim_id}' cannot be evaluated; supply it as an input "
                        'or use allow_missing_inputs=True.'
                    )
                return None
            visiting.add(dim_id)
            data = dict(inputs)
            for dep in dim.get_dependencies():
                data[dep.get_id()] = resolve(dep.get_id())
            visiting.discard(dim_id)
            return dim.evaluate(data)

        return resolve(output_dimension_id)
