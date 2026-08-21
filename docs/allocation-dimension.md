# AllocationDimension

A user-defined dimension that **distributes** spend across other dimensions rather than classifying it. An allocation describes how a pool of cost is split — by telemetry stream or by rule-based proportional / even allocation across dimension elements.

CloudZero docs: [CFDL Guide → Adding allocations](https://docs.cloudzero.com/docs/costformation-definition-language-guide#adding-allocations), [Allocation Short Form Rules](https://docs.cloudzero.com/docs/allocation-short-form-rules), [Element Cutoff Thresholds](https://docs.cloudzero.com/docs/element-cutoff-thresholds).

## Important: allocations are not evaluable

`AllocationDimension.evaluate(data)` raises `TypeError`. Allocation dimensions describe how the CloudZero billing system distributes spend — they have no Python-evaluable value. When a `CostFormation.evaluate()` call encounters an allocation in a dependency chain, supply its value in `inputs` to short-circuit the evaluation.

```python
# Will raise TypeError:
formation.evaluate({}, 'TelemetryAllocation')

# Works — input override bypasses evaluation:
formation.evaluate({'TelemetryAllocation': 'cost-per-user'}, 'AllocationCategory')
```

## Two allocation flavors

CFDL defines two allocation forms:

- **`AllocateByStreams`** — telemetry-driven. Optionally rate-based.
- **`AllocateByRules`** — distribute a chosen pool of spend across dimension elements, either `Proportional` or `Even`. Supports an optional second-level partition via `ForEachElementOf`.

Both forms accept an optional top-level `ElementCutoff` to bucket small elements.

---

### Telemetry (`AllocateByStreams`)

Simplest form — a list of telemetry stream names:

```python
class TelemetryAllocation(AllocationDimension):
    name = 'Telemetry Stream Allocation'
    streams = ['cost-per-request', 'cost-per-user']
```

```yaml
TelemetryAllocation:
  Type: Allocation
  Name: Telemetry Stream Allocation
  AllocateByStreams:
    Streams:
    - cost-per-request
    - cost-per-user
```

Add a `FixedRate` modifier for rate-based allocation:

```python
from costformation import FixedRate

class RateBasedTelemetry(AllocationDimension):
    streams = ['cost-per-gb']
    rate = FixedRate(value=0.1, default_element='other')
```

```yaml
RateBasedTelemetry:
  Type: Allocation
  AllocateByStreams:
    Streams:
    - cost-per-gb
    Rate:
      Type: Fixed
      Value: 0.1
      DefaultElement: other
```

`ElementCutoff` is **not supported** with rate-based streams.

---

### Rule-based (`AllocateByRules`)

Select the spend to allocate and distribute it across elements:

```python
from costformation import AcrossElements, Account, AllocationMethod, GroupRule, Service, SpendToAllocate

class RuleBasedAllocation(AllocationDimension):
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = [Service().equals('AmazonEC2')]                           # list shorthand
    across_elements = [GroupRule(name='by-account', condition=Account().begins_with('prod-'))]  # list shorthand
```

The list shorthand expands to `SpendToAllocate(conditions=[...])` and `AcrossElements(rules=[...])`. Use the explicit forms when you need more than conditions / rules:

```python
class RichAllocation(AllocationDimension):
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = SpendToAllocate(
        source=Service(),
        transforms=[Lower()],
        conditions=[Service().contains('AmazonEC2')],
    )
    across_elements = AcrossElements(
        source=Account(),
        groups={'production': [Account().begins_with('prod-')]},   # shorthand: Groups
    )
```

```yaml
RuleBasedAllocation:
  Type: Allocation
  AllocateByRules:
    AllocationMethod: Proportional
    SpendToAllocate:
      Conditions:
      - Equals: AmazonEC2
        Source: Service
    AcrossElements:
      Rules:
      - Type: Group
        Name: by-account
        Conditions:
        - BeginsWith: prod-
          Source: Account
```

### Advanced allocation method

For `Proportional` allocation only, you can override granularity and cost type:

```python
from costformation import AllocationMethod, Granularity, CostType, ProportionalMethod

allocation_method = ProportionalMethod(
    granularity=Granularity.USAGE_MONTHLY,
    cost_type=CostType.AMORTIZED,
)
```

Emits the dict form of `AllocationMethod`:

```yaml
AllocationMethod:
  Method: Proportional
  Granularity: UsageMonthly
  CostType: AmortizedCost
```

### ForEachElementOf

Proportional allocation only. Adds a second-level partition with the same shape as `AcrossElements`:

```python
from costformation import ForEachElementOf

class PartitionedAllocation(AllocationDimension):
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = [Service().equals('AmazonEC2')]
    across_elements = [GroupRule(name='by-account', condition=Account().begins_with('prod-'))]
    foreach_element_of = ForEachElementOf(
        rules=[GroupRule(name='by-region', condition=Region().equals('us-east-1'))],
    )
```

---

### ElementCutoff

Bucket elements whose combined allocation is below a threshold:

```python
from costformation import ElementCutoff

class BucketedAllocation(AllocationDimension):
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = [Service().equals('AmazonEC2')]
    across_elements = [GroupRule(name='by-account', condition=Account().begins_with('prod-'))]
    element_cutoff = ElementCutoff(threshold_percent=5, name='Other')
```

Emits as a top-level sibling of `AllocateByRules` / `AllocateByStreams`:

```yaml
BucketedAllocation:
  Type: Allocation
  AllocateByRules: {...}
  ElementCutoff:
    ThresholdPercent: 5
    Name: Other
```

`threshold_percent` must be in `[0, 100)`. `ElementCutoff` is forbidden with rate-based streams and with `AllocationMethod.EVEN`.

---

## Attributes

| Attribute | Type | Used by |
|-----------|------|---------|
| `name` | `str \| None` | All (optional display name) |
| `streams` | `list[str]` | `AllocateByStreams` |
| `rate` | `FixedRate \| None` | `AllocateByStreams` |
| `allocation_method` | `AllocationMethod \| ProportionalMethod \| None` | `AllocateByRules` (required) |
| `spend_to_allocate` | `SpendToAllocate \| list[Condition] \| None` | `AllocateByRules` (required when `allocation_method` is set) |
| `across_elements` | `AcrossElements \| list[Rule] \| None` | `AllocateByRules` (required when `allocation_method` is set) |
| `foreach_element_of` | `ForEachElementOf \| None` | `AllocateByRules` (Proportional only) |
| `element_cutoff` | `ElementCutoff \| None` | Either form |
| `hide` | `bool \| None` | Hide from UI |
| `disable` | `bool \| None` | Disable processing |

## Building blocks

These classes compose into the two allocation forms above.

### `SpendToAllocate`

Selects the pool of spend to distribute. Extends `_SourceInfoBlock` (source / sources / coalesce_sources / transforms) with a `conditions` list.

```python
SpendToAllocate(
    source=Service(),
    transforms=[Lower()],
    conditions=[Service().contains('ec2')],
)
```

### `AcrossElements` / `ForEachElementOf`

Selects the destination elements. Both extend `_SourceInfoBlock` and require exactly one of:

- `rules=[...]` — longhand (`Rules` key)
- `groups={name: [conditions, ...]}` — shorthand (`Groups` key)
- `group_by=GroupByRule(...)` — shorthand (`GroupBy` key)

`ForEachElementOf` is schema-identical to `AcrossElements` and inherits its behavior.

### `AllocationMethod`

String `Enum` — the simple form of `AllocationMethod:`:

- `AllocationMethod.PROPORTIONAL` → `Proportional`
- `AllocationMethod.EVEN` → `Even`

### `ProportionalMethod`

Advanced Proportional allocation spec with optional `Granularity` and `CostType`. Emits the dict form of `AllocationMethod:`.

### `Granularity`

String `Enum`: `USAGE_DAILY`, `BILLING_PERIOD`, `USAGE_MONTHLY`.

### `CostType`

String `Enum`: `BILLED`, `DISCOUNTED`, `AMORTIZED`, `DISCOUNTED_AMORTIZED`, `REAL`, `ON_DEMAND`, `INVOICED_AMORTIZED`, `USAGE_AMOUNT`, `CUSTOM`.

### `FixedRate`

Fixed-rate modifier for telemetry allocations. Attributes: `value: float`, `default_element: str`.

### `ElementCutoff`

Small-element cutoff. Attributes: `threshold_percent: float` (must be in `[0, 100)`), `name: str | None`.

## Validation

`AllocationDimension.to_dict()` raises `ValueError` on any of these invalid combinations:

- Both `streams` and `allocation_method` set
- `allocation_method` set without `spend_to_allocate` or `across_elements`
- `rate` combined with `element_cutoff`
- `AllocationMethod.EVEN` combined with `element_cutoff`
- `foreach_element_of` without Proportional `allocation_method`
