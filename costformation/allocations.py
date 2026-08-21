# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Allocation building blocks for AllocationDimension.

These types compose into the two allocation forms defined by CFDL:

- ``AllocateByStreams``: telemetry-driven allocation, optionally with a FixedRate.
- ``AllocateByRules``: distribute spend selected by SpendToAllocate across the
  elements selected by AcrossElements, using an AllocationMethod (proportional
  or even). ForEachElementOf adds a second-level partition for proportional
  allocation.

Both forms optionally take an ElementCutoff to bucket small elements.
"""

from enum import Enum
from typing import Any

# ``(str, Enum)`` is the pre-3.11 equivalent of ``StrEnum`` — each member is both
# a ``str`` and an ``Enum``, and ``member.value`` returns the raw string. We use
# this rather than ``enum.StrEnum`` so the library works on Python 3.10.


class AllocationMethod(str, Enum):
    """Allocation method for AllocateByRules."""

    PROPORTIONAL = 'Proportional'
    EVEN = 'Even'


class Granularity(str, Enum):
    """Granularity for ProportionalMethod."""

    USAGE_DAILY = 'UsageDaily'
    BILLING_PERIOD = 'BillingPeriod'
    USAGE_MONTHLY = 'UsageMonthly'


class CostType(str, Enum):
    """Cost type for ProportionalMethod."""

    BILLED = 'BilledCost'
    DISCOUNTED = 'DiscountedCost'
    AMORTIZED = 'AmortizedCost'
    DISCOUNTED_AMORTIZED = 'DiscountedAmortizedCost'
    REAL = 'RealCost'
    ON_DEMAND = 'OnDemandCost'
    INVOICED_AMORTIZED = 'InvoicedAmortizedCost'
    USAGE_AMOUNT = 'UsageAmount'
    CUSTOM = 'CustomCost'


class ProportionalMethod:
    """Advanced Proportional allocation spec with optional Granularity and CostType.

    Use ``AllocationMethod.PROPORTIONAL`` for the simple form (just the method),
    and ``ProportionalMethod(...)`` when you need to override Granularity or CostType.
    """

    def __init__(self, granularity: Granularity | None = None, cost_type: CostType | None = None):
        self.granularity = granularity
        self.cost_type = cost_type

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'Method': AllocationMethod.PROPORTIONAL.value}
        if self.granularity is not None:
            result['Granularity'] = self.granularity.value
        if self.cost_type is not None:
            result['CostType'] = self.cost_type.value
        return result


class FixedRate:
    """Fixed-rate modifier for AllocateByStreams."""

    def __init__(self, value: float, default_element: str):
        self.value = value
        self.default_element = default_element

    def to_dict(self) -> dict[str, Any]:
        return {'Type': 'Fixed', 'Value': self.value, 'DefaultElement': self.default_element}


class ElementCutoff:
    """Threshold for bucketing small elements into an 'other' group.

    ``threshold_percent`` must be in [0, 100). Forbidden with rate-based AllocateByStreams
    and with Even allocation method — AllocationDimension validates this.
    """

    def __init__(self, threshold_percent: float, name: str | None = None):
        if not 0 <= threshold_percent < 100:
            raise ValueError('threshold_percent must be in [0, 100)')
        self.threshold_percent = threshold_percent
        self.name = name

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'ThresholdPercent': self.threshold_percent}
        if self.name is not None:
            result['Name'] = self.name
        return result
