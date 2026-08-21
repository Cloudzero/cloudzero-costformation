# cloudzero-costformation

A Python library for building, serializing, and locally evaluating CloudZero [CostFormation Definition Language](https://docs.cloudzero.com/docs/costformation-definition-language-guide) (CFDL) files.

A CostFormation file describes how to allocate cloud spend into dimensions that have business meaning (environments, teams, cost buckets, ...). This library lets you author those dimensions as typed Python classes, emit the canonical YAML, and evaluate a formation against sample input data to sanity-check rule behavior before deploying.

## The shape of a CostFormation

Every CostFormation file is a collection of **dimensions**. Each dimension:

- Has an **ID** (its class name) that other dimensions reference.
- Reads one or more **source** dimensions — either cloud provider primitives like `Service` / `Account` / `Tag('Environment')`, or other user-defined dimensions.
- Applies zero or more **transforms** to normalize source values (lowercase, strip, split, ...).
- Evaluates an ordered list of **rules**, each matching on **conditions**, to produce a value.

Dimensions come in a few kinds:

| Kind | Purpose | Docs |
|------|---------|------|
| **Core** (`Service`, `Account`, `Tag`, ...) | Cloud-provider primitives. Referenced, never defined. | [core-dimensions.md](core-dimensions.md) |
| **Global** (`ServiceDisplay`, `Category`, ...) | CloudZero-managed. Referenced with a `CZ:Defined:` prefix. | [global-dimensions.md](global-dimensions.md) |
| **Group** (user-defined) | Classify spend into named groups via rules and conditions. | [group-dimension.md](group-dimension.md) |
| **Allocation** (user-defined) | Distribute spend across other dimensions via telemetry, proportional, or rule-based allocation. | [allocation-dimension.md](allocation-dimension.md) |

A [`CostFormation`](costformation.md) holds the list of user-defined dimensions and produces the final YAML.

## A minimal example

```python
from costformation import Account, BeginsWith, CostFormation, Equals, GroupDimension, GroupRule, Lower, Tag


class Environment(GroupDimension):
    source = Tag('Environment')
    transforms = [Lower()]
    rules = [
        GroupRule(name='production', condition=BeginsWith('prod')),
        GroupRule(name='development', condition=BeginsWith('dev') | Equals('test')),
        GroupRule(name='production', condition=Account().begins_with('prod-')),
    ]
    default_value = 'unknown'


formation = CostFormation([Environment()])
```

## Generating YAML with `to_yaml()`

`CostFormation.to_yaml()` serializes the formation to the canonical CFDL YAML format that CloudZero ingests:

```python
print(formation.to_yaml())
```

```yaml
Dimensions:
  Environment:
    Source: Tag:Environment
    Transforms:
    - Type: Lower
    Rules:
    - Type: Group
      Name: production
      Conditions:
      - BeginsWith: prod
    - Type: Group
      Name: development
      Conditions:
      - BeginsWith: dev
      - Equals: test
    - Type: Group
      Name: production
      Conditions:
      - BeginsWith: prod-
        Source: Account
    DefaultValue: unknown
```

## Evaluating locally with `evaluate()`

`CostFormation.evaluate(inputs, output_dimension_id)` runs the rules locally so you can check behavior against sample billing rows without uploading to CloudZero. It transitively resolves any dependent dimensions.

```python
formation.evaluate({'Tag:Environment': 'PRODUCTION'}, 'Environment')
# 'production'

formation.evaluate({'Account': 'prod-billing'}, 'Environment')
# 'production'  (via the Account fallback rule)

formation.evaluate({}, 'Environment', allow_missing_inputs=True)
# 'unknown'  (default_value)
```

### Input priority

Values supplied in `inputs` take priority over evaluation — for both core dimensions (Service, Account, ...) and dimensions defined in the formation. This lets you override a precomputed upstream value or bypass an `AllocationDimension` (which is not evaluable and would otherwise raise):

```python
formation.evaluate({'Environment': 'manual-override'}, 'Environment')
# 'manual-override'
```

### Missing inputs

By default, `evaluate()` raises `ValueError` if it needs a value that wasn't supplied. Pass `allow_missing_inputs=True` to treat missing inputs as `None` (letting rules fall through to defaults):

```python
formation.evaluate({}, 'Environment')
# ValueError: Required input 'Tag:Environment' was not provided

formation.evaluate({}, 'Environment', allow_missing_inputs=True)
# 'unknown'
```

### Cycles

Cyclic dependencies raise `ValueError` during resolution. Supplying an intermediate value in `inputs` breaks the cycle because the input short-circuits evaluation.

## Where to go next

- **[reference.md](reference.md)** — Alphabetical index of every class.
- **[costformation.md](costformation.md)** — The top-level container and its `to_yaml` / `evaluate` methods.
- **[group-dimension.md](group-dimension.md)** — Author your own classified dimensions.
- **[allocation-dimension.md](allocation-dimension.md)** — Telemetry, proportional, and rule-based allocations.
- **[conditions.md](conditions.md)** — `Equals`, `BeginsWith`, `And`, `Or`, `HasValue`, and more.
- **[rules.md](rules.md)** — `Rule` (abstract), `GroupRule`, `GroupByRule`, `MetadataRule`.
- **[transforms.md](transforms.md)** — `Lower`, `Upper`, `Clean`, `Normalize`, `Split`, ...
- **[core-dimensions.md](core-dimensions.md)** — The cloud-provider primitives you reference as sources.
- **[global-dimensions.md](global-dimensions.md)** — CloudZero-managed dimensions (`ServiceDisplay`, `Category`, ...).
- **[ref.md](ref.md)** — `Ref`: reference a dimension that lives outside this file.

For the full CloudZero CFDL specification, see the [CFDL Reference](https://docs.cloudzero.com/docs/cfdl-reference) and the [CFDL Guide](https://docs.cloudzero.com/docs/costformation-definition-language-guide).
