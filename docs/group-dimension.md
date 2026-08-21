# GroupDimension

A user-defined classified dimension. Reads source values from one or more upstream dimensions, optionally normalizes them via transforms, and runs ordered rules to produce a named output group.

CloudZero docs: [CFDL Reference → Custom Dimensions](https://docs.cloudzero.com/docs/cfdl-reference#custom-dimensions) and [CFDL Guide → Defining a Custom Dimension](https://docs.cloudzero.com/docs/costformation-definition-language-guide#defining-a-custom-dimension).

## Defining a GroupDimension

Subclass `GroupDimension` and set the class attributes. The class name becomes the dimension's ID and is used as the data-dict key when other dimensions reference it.

```python
from costformation import Account, BeginsWith, Equals, GroupDimension, GroupRule, Lower, Tag


class Environment(GroupDimension):
    name = 'Environment Classification'      # optional display name
    source = Tag('Environment')               # upstream source
    transforms = [Lower()]                    # applied before rules
    rules = [
        GroupRule(name='production', condition=BeginsWith('prod')),
        GroupRule(name='development', condition=BeginsWith('dev') | Equals('test')),
        GroupRule(name='production', condition=Account().begins_with('prod-')),
    ]
    default_value = 'unknown'
```

## Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `id` | `str \| None` | Optional explicit dimension ID. Defaults to the class name. Use this when the desired ID isn't a valid Python identifier (e.g. hyphenated like `cost-center`). |
| `name` | `str \| None` | Optional display name emitted as YAML `Name:`. Defaults to the class name. |
| `source` | `Dimension \| list[Dimension] \| None` | Upstream source(s). If a list, the first is the primary source used for sourceless conditions; all are declared as dependencies. |
| `transforms` | `list[Transform]` | Applied to the source value before rule evaluation. |
| `rules` | `list[Rule]` | Any concrete `Rule` subclass (`GroupRule`, `GroupByRule`, `MetadataRule`); evaluated in order, first non-`None` result wins. |
| `default_value` | `str \| None` | Returned when no rule matches. If unset, unmatched evaluation returns `None`. |
| `child` | `Dimension \| None` | Hierarchical child dimension (emitted as YAML `Child:`). |
| `override` | `Dimension \| None` | Dimension whose values this one overrides (YAML `Override:`). |
| `hide` | `bool \| None` | Hide this dimension from the CloudZero UI. |
| `disable` | `bool \| None` | Disable processing for this dimension. |

## Condition helpers on the instance

`GroupDimension` inherits the condition-builder helpers from `Dimension`. Call them on an instance to build a source-bound condition:

```python
env = Environment()
env.equals('production')              # Equals('production', source=env)
env.begins_with('prod')               # BeginsWith('prod', source=env)
env.has_value(False)                  # HasValue(False, source=env)
env.matches(r'^prod-\d+$')            # Matches(..., source=env)
env.contains('prod')                  # Contains('prod', source=env)
env.ends_with('-prod')                # EndsWith('-prod', source=env)
env.before('N') / env.after('A')      # lexicographic
env.before_or_equals(...) / env.after_or_equals(...)
```

The same helpers are available on every `Dimension` subclass (core, global, group, allocation, Ref).

## Evaluation semantics

`GroupDimension.evaluate(data)` runs as follows:

1. If `source` and `transforms` are both set, apply transforms to `data[primary_source.get_id()]` in a local copy of `data`.
2. Walk `rules` in order. Each rule sees the (possibly transformed) data and the primary source:
   - **`GroupRule`** — evaluates its condition; if True, returns `rule.name`.
   - **`GroupByRule`** — returns the dynamic group name (source value, post-transform).
   - **`MetadataRule`** — returns the matched substring or hierarchical-pattern output.
3. If no rule matches, returns `default_value` (or `None` if unset).

Rules are skipped if the dimension has no `source` set and the rule itself doesn't carry a source override.

See [rules.md](rules.md) for each rule type in detail.

## Dimension base class

`GroupDimension` inherits from the abstract `Dimension` base class, which also has:

- `get_id() -> str` — the class name (used as the YAML key and data-dict key).
- `get_name() -> str` — `name` if set, else `get_id()`.
- `get_reference() -> str` — `User:Defined:<id>`, used when another dimension references this one in YAML.
- `get_dependencies() -> list[Dimension]` — all dimensions this one reads during evaluation (source + rule deps); used by `CostFormation.evaluate` for dependency resolution.

You normally subclass `GroupDimension` (for classified output) or `AllocationDimension` (for allocation); the abstract `Dimension` / `CoreDimension` / `GlobalDimension` classes are internal building blocks.
