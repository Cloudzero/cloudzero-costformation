# Ref

`Ref` is a utility that lets you reference a dimension by its fully-qualified YAML ID without defining it in Python. It's intended for **testing in isolation** — letting you author a `GroupDimension` whose source is a dimension defined in a different CostFormation file, without importing or redefining that dimension.

`Ref` has no YAML representation on its own: calling `to_dict()` on a `Ref` raises `TypeError`. Its only job is to emit its `reference_id` verbatim when another dimension references it.

## Constructor

```python
Ref(reference_id: str)
```

`reference_id` is the fully-qualified ID as it would appear in YAML:

| Prefix / shape | Dimension kind |
|----------------|----------------|
| `Service`, `Account`, `Region`, ... | Core dimension |
| `Tag:<key>` | Tag dimension |
| `K8s:Cluster`, `K8s:Namespace`, `K8s:Label:<name>` | Kubernetes dimension |
| `CZ:Defined:<ClassName>` | Global dimension |
| `User:Defined:<ClassName>` | User-defined (group or allocation) dimension |

## Usage

```python
from costformation import GroupDimension, GroupRule, Ref


class MyDimension(GroupDimension):
    # Reference a user-defined dimension that lives in a different CF file
    source = Ref('User:Defined:SomeOtherDimension')
    rules = [
        GroupRule(name='match', condition=Ref('User:Defined:SomeOtherDimension').equals('value')),
    ]
```

The emitted YAML will contain `Source: User:Defined:SomeOtherDimension` verbatim. CloudZero resolves the reference at ingestion time.

## When to prefer defining a real dimension

Use `Ref` sparingly — it bypasses type safety and dependency tracking. When possible, import or redefine the upstream dimension so that `CostFormation.evaluate()` can resolve the full dependency chain. A `Ref`-sourced dimension can only be evaluated if you supply the referenced value in `inputs`.

No CloudZero docs anchor — `Ref` is a Python-side construct with no CFDL counterpart.
