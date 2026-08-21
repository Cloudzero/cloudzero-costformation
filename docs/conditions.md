# Conditions

Conditions are the predicates that drive a `GroupRule` and the gating clauses on `GroupByRule` / `MetadataRule`. They evaluate against a data dict and a source dimension, returning `True` / `False`. Conditions can be composed with Python's `&` (AND), `|` (OR), and `~` (NOT) operators.

CloudZero docs: [CFDL Reference → Conditions](https://docs.cloudzero.com/docs/cfdl-reference#conditions).

## Sourcing

Most conditions accept a `source=` or `sources=` argument:

- `source=SomeDimension()` — read the value from `data[SomeDimension().get_id()]`.
- `sources=[A(), B()]` — evaluate against each source in turn; the condition is satisfied if ANY source's value matches (OR semantics). Supported by every value condition (`Equals`, `Contains`, `BeginsWith`, `EndsWith`, `Matches`, `Before`/`After` variants, `HasValue`).
- No source — the condition inherits the source of the rule / dimension it lives inside.

`source` and `sources` are mutually exclusive.

## Composition via operators

```python
# And:  cond1 & cond2           → And(cond1, cond2)
# Or:   cond1 | cond2           → Or(cond1, cond2)
# Not:  ~cond                   → Not(cond)

Service().equals('AmazonEC2') & Account().begins_with('prod-')
Service().equals('AmazonEC2') | Service().equals('AmazonS3')
~Service().equals('AmazonEC2')
```

---

## `And`

Logical AND of one or more conditions.

CloudZero docs: [cfdl-reference#and](https://docs.cloudzero.com/docs/cfdl-reference#and).

```python
And(cond1, cond2, ...)
# or
cond1 & cond2
```

Serializes to `{'And': [...]}`. All children must evaluate `True`.

---

## `Or`

Logical OR of one or more conditions.

CloudZero docs: [cfdl-reference#or](https://docs.cloudzero.com/docs/cfdl-reference#or).

```python
Or(cond1, cond2, ...)
# or
cond1 | cond2
```

Serializes to `{'Or': [...]}`. At least one child must evaluate `True`.

Note: when a `GroupRule`'s top-level condition is an `Or`, the YAML flattens its children into the `Conditions:` list (implicit OR) rather than emitting a nested `Or:` block.

---

## `Not`

Negates a single condition.

CloudZero docs: [cfdl-reference#not](https://docs.cloudzero.com/docs/cfdl-reference#not).

```python
Not(cond)
# or
~cond
```

Serializes to `{'Not': [cond.to_dict()]}`.

---

## `Equals`

Exact match (scalar or any-of-list).

CloudZero docs: [cfdl-reference#equals](https://docs.cloudzero.com/docs/cfdl-reference#equals).

```python
Equals('AmazonEC2', source=Service())
Equals(['AmazonEC2', 'AmazonS3'], source=Service())   # any-of
Service().equals('AmazonEC2')                          # helper form
```

Returns `False` if the source value is missing from `data`.

---

## `Contains`

Substring match (scalar or any-of-list).

CloudZero docs: [cfdl-reference#contains](https://docs.cloudzero.com/docs/cfdl-reference#contains).

```python
Contains('EC2', source=Service())
Contains(['EC2', 'S3'], source=Service())
Service().contains('EC2')
```

---

## `BeginsWith`

Prefix match (scalar or any-of-list).

CloudZero docs: [cfdl-reference#beginswith](https://docs.cloudzero.com/docs/cfdl-reference#beginswith).

```python
BeginsWith('Amazon', source=Service())
Service().begins_with('Amazon')
```

---

## `EndsWith`

Suffix match (scalar or any-of-list).

CloudZero docs: [cfdl-reference#endswith](https://docs.cloudzero.com/docs/cfdl-reference#endswith).

```python
EndsWith('EC2', source=Service())
Service().ends_with('EC2')
```

---

## `Matches`

Regular-expression match. Evaluation mirrors Snowflake's default `RLIKE`, which the condition compiles to in production.

- CloudZero docs: [cfdl-reference#matches](https://docs.cloudzero.com/docs/cfdl-reference#matches)
- Snowflake regex reference: [Regular expression functions](https://docs.snowflake.com/en/sql-reference/functions-regexp)

### Examples

```python
# Exact match (auto-anchored)
Matches(r'AmazonEC2', source=Service())

# Prefix / suffix / substring — use explicit .*
Service().matches(r'Amazon.*')
Service().matches(r'.*EC2')
Service().matches(r'.*EC2.*')

# Alternation — each branch is full-matched
Service().matches(r'AmazonEC2|AmazonS3|AmazonRDS')

# Escape metacharacters to match them literally
Tag('aws:cloudformation:stack-name').matches(r'my-stack-v\d+')   # my-stack-v1, my-stack-v42
UsageType().matches(r'USW2-BoxUsage:t3\.medium')                 # literal dot in 't3.medium'
Resource().matches(r's3://example-bucket/.*')                 # slashes are literal; . escaped if meant literally

# Backslash-shortcut character classes (ASCII-only)
Tag('BuildID').matches(r'\w+-\d{4}')                             # word chars, dash, 4 digits
Account().matches(r'\d{12}')                                     # AWS account ID
Tag('Email').matches(r'[\w.-]+@[\w.-]+\.\w+')                    # simple email

# POSIX bracket classes (equivalent, clearer intent)
Service().matches(r'[[:alpha:]]+[[:digit:]]+')                   # letters then digits
Tag('Slug').matches(r'[[:lower:][:digit:]-]+')                   # kebab-case slug

# Word boundaries
Service().matches(r'.*\bEC2\b.*')

# Quantifier ranges (remember: the whole value must fit)
Resource().matches(r'i-[[:xdigit:]]{8,17}')                      # EC2 instance ID
```

### Snowflake-compatible semantics

- **Full-string match** — Snowflake auto-anchors every pattern. In Python we use `re.fullmatch`, so `'Amazon'` does **not** match `'AmazonEC2'`; use `'Amazon.*'` if you want prefix semantics.
- **Case-sensitive, single-line** — no flags are passed to `RLIKE`, and `.` does not match newline.
- **ASCII-only shorthand classes** — `\d`, `\w`, `\s` match only ASCII. Fullwidth digit `'５'` is not a `\d`.
- **POSIX bracket classes** (`[[:alpha:]]`, `[[:digit:]]`, `[[:alnum:]]`, `[[:upper:]]`, `[[:lower:]]`, `[[:space:]]`, `[[:blank:]]`, `[[:xdigit:]]`, `[[:punct:]]`, `[[:cntrl:]]`, `[[:print:]]`, `[[:graph:]]`) are supported — the library translates them to ASCII equivalents before compiling.

### Rejected at construction time

The following Python-regex features are rejected with `ValueError` because Snowflake either errors on them or accepts-but-ignores them, leading to silent divergence between local evaluation and production:

- Lookarounds: `(?=...)`, `(?!...)`, `(?<=...)`, `(?<!...)`
- Named groups / backrefs: `(?P<name>...)`, `(?P=name)`
- Inline flags / modifiers: `(?i)`, `(?s)`, `(?m)`, `(?x)`, `(?a)`, scoped `(?i:...)`
- Inline comments: `(?#...)`
- Backreferences in the match pattern: `\1` – `\9`
- Non-greedy quantifiers: `*?`, `+?`, `??`, `}?`

Use POSIX bracket classes or plain character classes for Unicode/Locale concerns; use explicit alternation or `.*?` substitutes where you'd reach for non-greedy.

Exposes the original (pre-translation) pattern via the `.pattern` property.

---

## `Before`

Lexicographic strict-before comparison (`actual < value`).

CloudZero docs: [cfdl-reference#before](https://docs.cloudzero.com/docs/cfdl-reference#before).

```python
Before('N', source=Service())
Service().before('N')
```

---

## `BeforeOrEquals`

Lexicographic before-or-equal comparison (`actual <= value`).

CloudZero docs: [cfdl-reference#beforeorequals](https://docs.cloudzero.com/docs/cfdl-reference#beforeorequals).

```python
BeforeOrEquals('N', source=Service())
Service().before_or_equals('N')
```

---

## `After`

Lexicographic strict-after comparison (`actual > value`).

CloudZero docs: [cfdl-reference#after](https://docs.cloudzero.com/docs/cfdl-reference#after).

```python
After('A', source=Service())
Service().after('A')
```

---

## `AfterOrEquals`

Lexicographic after-or-equal comparison (`actual >= value`).

CloudZero docs: [cfdl-reference#afterorequals](https://docs.cloudzero.com/docs/cfdl-reference#afterorequals).

```python
AfterOrEquals('A', source=Service())
Service().after_or_equals('A')
```

Lexicographic comparisons are useful for date-string windows (`UsageDay`), alphabetical partitions, etc.

---

## `HasValue`

Tests whether a dimension's value is non-null and non-empty.

CloudZero docs: [cfdl-reference#hasvalue](https://docs.cloudzero.com/docs/cfdl-reference#hasvalue).

```python
HasValue(source=Tag('Environment'))              # True if tag has a value
HasValue(True, source=Tag('Environment'))        # same
HasValue(False, source=Tag('Environment'))       # True if tag is null/empty
HasValue(sources=[Tag('Environment'), Tag('env')])   # True if ANY has a value
Tag('Environment').has_value()                   # helper form
Tag('Environment').has_value(False)
```

A value of `''` (empty string) is treated as "no value."

---

## `ForDateRange`

Restrict evaluation to billing rows within a date window.

CloudZero docs: [cfdl-reference#fordaterange](https://docs.cloudzero.com/docs/cfdl-reference#fordaterange).

```python
ForDateRange('2025-01-01', '2025-12-31')
ForDateRange(from_date='2025-01-01', until_date='2025-12-31')
```

Emits `{'ForDateRange': {'From': '...', 'Until': '...'}}`. For local testing, this condition returns `True` if both dates are non-empty; in production CloudZero checks against the actual billing-row date.

`ForDateRange` has no source dimension — it's not composable with `HasValue`-style source helpers.
