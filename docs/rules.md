# Rules

Rules live inside a `GroupDimension`'s `rules` list. Each rule maps matching rows to an output group. Rules are evaluated in order; the first rule that produces a non-`None` result wins.

CloudZero docs: [CFDL Guide → Rule types](https://docs.cloudzero.com/docs/costformation-definition-language-guide#rule-types).

## Class hierarchy

`Rule` is the abstract base; concrete rule types are subclasses.

```
Rule (abstract)
├── GroupRule       — Type: Group
├── GroupByRule     — Type: GroupBy
└── MetadataRule    — Type: Metadata
```

Anywhere a rule is accepted (`GroupDimension.rules`, `AcrossElements.rules`, `AllocationDimension.across_elements`), any concrete subclass works.

All three share `Source` / `Sources` / `CoalesceSources`. `Transforms` is supported by `GroupRule` and `GroupByRule` only — `MetadataRule` does not support transforms per CFDL.

| Key | GroupRule | GroupByRule | MetadataRule |
|-----|-----------|-------------|--------------|
| `Source` / `Sources` | ✓ | ✓ | ✓ |
| `CoalesceSources` | ✓ | ✓ | ✓ |
| `Transforms` | ✓ | ✓ | — |
| `Conditions` | ✓ (single) | ✓ (list) | ✓ (list) |
| `Name` | ✓ | — | — |
| `Format` | — | ✓ | ✓ |
| `Values` | — | — | ✓ |

---

## `GroupRule`

Classifies a matching row into a named group.

CloudZero docs: [CFDL Guide → Group rules](https://docs.cloudzero.com/docs/costformation-definition-language-guide#group-rules).

### Constructor

```python
GroupRule(
    name: str,
    condition: Condition,
    *,
    source: Dimension | None = None,
    sources: list[Dimension] | None = None,
    coalesce_sources: bool = False,
    transforms: list[Transform] | None = None,
)
```

`source` and `sources` are mutually exclusive.

| Argument | Purpose |
|----------|---------|
| `name` | The output group name — returned by `evaluate` when the condition matches. If empty, no `Name:` is emitted. |
| `condition` | The condition that triggers this rule. Compose with `&` / `\|` / `~`. |
| `source` | Optional single-source override. When set, sourceless conditions in this rule resolve against it instead of the dimension's source. |
| `sources` | Optional multi-source override (emitted as YAML `Sources:`). The first source is used as the primary for sourceless conditions. |
| `coalesce_sources` | With `sources`, emits `CoalesceSources: true` so CFDL uses the first non-null value across sources. |
| `transforms` | Transforms applied to the source value before evaluating the condition (in addition to any dimension-level transforms). |

### Example

```python
from costformation import Account, BeginsWith, Equals, GroupRule, Service

GroupRule(name='production', condition=BeginsWith('prod'))
GroupRule(name='prod-ec2',   condition=Service().equals('AmazonEC2') & Account().begins_with('prod-'))
GroupRule(name='ec2',        condition=Equals('AmazonEC2'), source=Service())
```

### YAML

```yaml
- Type: Group
  Name: prod-ec2
  Conditions:
  - And:
    - Equals: AmazonEC2
      Source: Service
    - BeginsWith: prod-
      Source: Account
```

An `Or(...)` at the top level of a rule's condition flattens into the `Conditions:` list (YAML's implicit-OR semantics).

---

## `GroupByRule`

Produces one output group per distinct value of the source dimension. Useful when you want to preserve the upstream granularity rather than bucket it.

CloudZero docs: [CFDL Guide → GroupBy rules](https://docs.cloudzero.com/docs/costformation-definition-language-guide#groupby-rules).

### Constructor

```python
GroupByRule(
    *,
    source: Dimension | list[Dimension] | None = None,
    sources: list[Dimension] | None = None,
    coalesce_sources: bool = False,
    transforms: list[Transform] | None = None,
    conditions: list[Condition] | None = None,
    format: str | None = None,
)
```

Exactly one of `source` or `sources` must be specified.

| Argument | Purpose |
|----------|---------|
| `source` | Single dimension, or a list of dimensions for use with multi-placeholder `format` (`'{0} - {1}'`). |
| `sources` | Multiple sources. Without `coalesce_sources`, each produces its own group. With `coalesce_sources=True`, sources are tried in order and the first non-null is used. |
| `coalesce_sources` | See above. |
| `transforms` | Applied to the source value before producing the group name. |
| `conditions` | Gating conditions — if any is false, the rule produces no group. |
| `format` | Optional format string (e.g., `'svc: {0}'`) applied to the final group name. |

### Example

```python
from costformation import GroupByRule, Normalize, Tag

GroupByRule(
    source=Tag('Team'),
    transforms=[Normalize()],
    conditions=[Tag('Team').has_value()],
)
```

### YAML

```yaml
- Type: GroupBy
  Source: Tag:Team
  Transforms:
  - Type: Normalize
  Conditions:
  - HasValue: true
    Source: Tag:Team
```

### Evaluation

`GroupByRule.evaluate(data, dim_source)` returns the (coalesced, transformed, formatted) source value if all conditions pass and the source has a value; otherwise `None`.

---

## `MetadataRule`

Searches source values for substring matches against a list of patterns. Patterns may be plain strings (match → return the matched string) or hierarchical dicts (match → return the parent key). Ideal for categorizing services, resource types, or product families.

CloudZero docs: [CFDL Guide → Metadata rules](https://docs.cloudzero.com/docs/costformation-definition-language-guide#metadata-rules).

### Constructor

```python
MetadataRule(
    source: Dimension | list[Dimension] | None = None,
    values: list[str | dict[str, list[str]]] | None = None,
    *,
    sources: list[Dimension] | None = None,
    coalesce_sources: bool = False,
    format: str | None = None,
    conditions: list[Condition] | None = None,
)
```

Exactly one of `source` or `sources` must be specified; `values` is required.

| Argument | Purpose |
|----------|---------|
| `source` | One dimension or a list of dimensions to search (emitted as YAML `Source: ...`). |
| `sources` | Alternative to `source` (emitted as YAML `Sources:`); pair with `coalesce_sources` for first-non-null semantics. |
| `coalesce_sources` | With `sources`, emits `CoalesceSources: true`. |
| `values` | Ordered list of patterns. Plain strings match as substrings; dicts are `{output_name: [substring, ...]}` — any substring match yields `output_name`. |
| `format` | Optional format string applied to the returned name. |
| `conditions` | Gating conditions — all must pass, else the rule produces no match. |

`MetadataRule` does **not** accept `transforms` — passing it raises `TypeError`.

### Example

```python
from costformation import MetadataRule, Service

MetadataRule(
    Service(),
    [
        {'compute': ['EC2', 'Lambda', 'Fargate']},
        {'storage': ['S3', 'EBS', 'EFS']},
        {'database': ['RDS', 'DynamoDB', 'Redshift']},
        'CloudFront',                       # plain string also works
    ],
)
```

### YAML

```yaml
- Type: Metadata
  Source: Service
  Values:
  - compute:
    - EC2
    - Lambda
    - Fargate
  - storage:
    - S3
    - EBS
    - EFS
  - database:
    - RDS
    - DynamoDB
    - Redshift
  - CloudFront
```

### Evaluation

Sources are checked in order; the first source with a value is used. Patterns are checked in order; the first pattern with a substring hit returns. If `format` is set, the returned name is run through `format.format(name)`.
