# Transforms

Transforms normalize a source value before it's evaluated against conditions. They can be applied at the dimension level (to every rule's source value) or at the rule level (to a specific rule's source).

CloudZero docs: [CFDL Reference → Transforms](https://docs.cloudzero.com/docs/cfdl-reference#transforms).

All transforms are stateless — `apply(value) -> str`. They serialize to `{'Type': '<Name>', ...}`.

```python
class MyDim(GroupDimension):
    source = Tag('Environment')
    transforms = [Lower(), Trim()]            # applied in order
    rules = [...]
```

---

## `Lower`

Convert to lowercase.

CloudZero docs: [cfdl-reference#lower](https://docs.cloudzero.com/docs/cfdl-reference#lower).

```python
Lower().apply('AmazonEC2')   # 'amazonec2'
```

```yaml
- Type: Lower
```

---

## `Upper`

Convert to UPPERCASE.

CloudZero docs: [cfdl-reference#upper](https://docs.cloudzero.com/docs/cfdl-reference#upper).

```python
Upper().apply('AmazonEC2')   # 'AMAZONEC2'
```

```yaml
- Type: Upper
```

---

## `Title`

Convert to Title Case.

CloudZero docs: [cfdl-reference#title](https://docs.cloudzero.com/docs/cfdl-reference#title).

```python
Title().apply('amazon ec2')   # 'Amazon Ec2'
```

```yaml
- Type: Title
```

---

## `Trim`

Strip leading and trailing whitespace.

CloudZero docs: [cfdl-reference#trim](https://docs.cloudzero.com/docs/cfdl-reference#trim).

```python
Trim().apply('  padded  ')   # 'padded'
```

```yaml
- Type: Trim
```

---

## `Clean`

Strip whitespace, then replace runs of non-word characters with dashes, then strip leading/trailing dashes.

CloudZero docs: [cfdl-reference#clean](https://docs.cloudzero.com/docs/cfdl-reference#clean).

```python
Clean().apply('Hello, World!')           # 'Hello-World'
Clean().apply('  ---wrapped---  ')       # 'wrapped'
Clean().apply('multiple   spaces')       # 'multiple-spaces'
```

```yaml
- Type: Clean
```

---

## `Normalize`

Trim, lowercase, then `Clean`-style dash-ification. The canonical way to turn user-supplied tag values into slugs.

CloudZero docs: [cfdl-reference#normalize](https://docs.cloudzero.com/docs/cfdl-reference#normalize).

```python
Normalize().apply('  Data Platform  ')   # 'data-platform'
Normalize().apply('AI Research')         # 'ai-research'
```

```yaml
- Type: Normalize
```

---

## `Split`

Split the value on a delimiter and return the substring at the given index. Returns the original value if `index` is out of range.

CloudZero docs: [cfdl-reference#split](https://docs.cloudzero.com/docs/cfdl-reference#split).

### Constructor

```python
Split(delimiter: str, index: int, maxsplit: int | None = None)
```

| Argument | Purpose |
|----------|---------|
| `delimiter` | Substring to split on. |
| `index` | Zero-based index to return. |
| `maxsplit` | Optional cap on the number of splits (mirrors Python's `str.split(..., maxsplit)`). When set, trailing parts are joined — useful for "prefix vs. rest." |

### Example

```python
Split('/', 0).apply('a/b/c')                 # 'a'
Split('/', 2).apply('a/b/c')                 # 'c'
Split('/', 5).apply('a/b/c')                 # 'a/b/c'  (out of range → original)
Split('/', 1, maxsplit=1).apply('a/b/c/d')   # 'b/c/d'  (rest after first split)
Split('/', 0).apply('no-delim')              # 'no-delim'
```

```yaml
- Type: Split
  Delimiter: /
  Index: 1
  Maxsplit: 2     # only when set
```

---

## `Lookup`

Resolve a value from a named key. In production CFDL the key is resolved server-side; the library's local `apply` treats the value as a serialized JSON object and returns the string stored under `key`. When the value is not a JSON object, the key is absent, or its value is not a string, `apply` returns `''` — matching how the other transforms model no-value (production wraps it in `NULLIF`).

CloudZero docs: [CFDL Reference → Transforms](https://docs.cloudzero.com/docs/cfdl-reference#transforms).

### Constructor

```python
Lookup(key: str)
```

| Argument | Purpose |
|----------|---------|
| `key` | The key to resolve from the deserialized value. |

### Example

```python
Lookup('name').apply('{"name": "AmazonEC2", "id": "i-123"}')   # 'AmazonEC2'
Lookup('name').apply('{"id": "i-123"}')                         # ''  (key absent)
Lookup('name').apply('not-a-dict')                             # ''  (not a JSON object)
```

```yaml
- Type: Lookup
  Key: name
```
