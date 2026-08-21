# CostFormation

The top-level container. A `CostFormation` holds the list of user-defined `GroupDimension` and `AllocationDimension` instances and provides the two operations you'll use most: serialize to YAML, and evaluate against sample inputs.

CloudZero docs: [CFDL Guide → CostFormation Definition File](https://docs.cloudzero.com/docs/costformation-definition-language-guide#costformation-definition-file).

## Constructor

```python
CostFormation(dimensions: list[Dimension])
```

`dimensions` is the ordered list of user-defined dimensions. Order is preserved in the emitted YAML.

## `to_yaml() -> str`

Serializes the formation to the canonical CFDL YAML that CloudZero ingests.

```python
from costformation import CostFormation, Equals, GroupDimension, GroupRule, Service


class Compute(GroupDimension):
    source = Service()
    rules = [GroupRule(name='ec2', condition=Equals('AmazonEC2'))]


print(CostFormation([Compute()]).to_yaml())
```

```yaml
Dimensions:
  Compute:
    Source: Service
    Rules:
    - Type: Group
      Name: ec2
      Conditions:
      - Equals: AmazonEC2
```

## `to_dict() -> dict`

Returns the same structure as `to_yaml()` but as a Python dict — useful for diffing, round-tripping, or embedding in larger documents.

## `evaluate(inputs, output_dimension_id, allow_missing_inputs=False) -> str | None`

Evaluates `output_dimension_id` against `inputs` locally, transitively resolving any dependent dimensions in the formation.

### Parameters

| Name | Type | Purpose |
|------|------|---------|
| `inputs` | `dict` | Dimension-ID to value mapping. Values are used as-is and short-circuit evaluation — both for core dimensions (Tag, Service, ...) and for user-defined dimensions defined in this formation. |
| `output_dimension_id` | `str` | The ID of the dimension to evaluate. Must exist in the formation or `ValueError` is raised. |
| `allow_missing_inputs` | `bool` | Default `False`: raise `ValueError` if a referenced dimension is neither in `inputs` nor in the formation. `True`: treat missing inputs as `None` and let rules fall through to defaults. |

### Resolution algorithm

For each dependency of the target dimension, `evaluate` recursively:

1. Returns the supplied `inputs` value if the dimension ID is present there.
2. Otherwise returns `None` (or raises, per `allow_missing_inputs`) if the ID is not in the formation.
3. Otherwise recursively resolves the dimension's own dependencies, then calls the dimension's `evaluate` method.

Results for a single `evaluate` call are memoized, so a dimension that appears in multiple dependency chains is only resolved once per call.

### Input priority and overrides

Supplying a value for a dimension defined in the formation bypasses its evaluation entirely. This is useful for:

- **Precomputed upstream values** — when you already have an environment classification from another process.
- **Testing downstream behavior** — pin an upstream dim to a specific value to exercise a particular rule path.
- **Bypassing an `AllocationDimension`** — allocation dimensions are not evaluable and will raise `TypeError` if encountered. Supplying their value as input lets downstream group dimensions proceed.

```python
# Override the computed value for 'Environment':
formation.evaluate({'Environment': 'override'}, 'CostBucket')

# Skip an AllocationDimension that a downstream dim references:
formation.evaluate({'TelemetryAllocation': 'cost-per-user'}, 'AllocationCategory')
```

### Missing-input behavior

```python
# Strict (default) — raises if anything required isn't supplied:
formation.evaluate({}, 'Environment')
# ValueError: Required input 'Tag:Environment' was not provided

# Lenient — missing inputs become None, rules fall through to defaults:
formation.evaluate({}, 'Environment', allow_missing_inputs=True)
# 'unknown'
```

`None` is a valid result (a dimension with no matching rule and no `default_value` legitimately resolves to `None`) and is recorded in the data dict for downstream conditions to observe via `HasValue(False, source=...)`.

### Cycle detection

Cyclic dependencies raise `ValueError` with the cycle's entry-point dimension named. Supplying a value for any dimension in the cycle breaks it, since the input short-circuits resolution before the recursive step.
