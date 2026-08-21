# cloudzero-costformation

[![PyPI](https://img.shields.io/pypi/v/cloudzero-costformation)](https://pypi.org/project/cloudzero-costformation/)
[![Python versions](https://img.shields.io/pypi/pyversions/cloudzero-costformation)](https://pypi.org/project/cloudzero-costformation/)
[![CI](https://github.com/Cloudzero/cloudzero-costformation/actions/workflows/ci.yml/badge.svg)](https://github.com/Cloudzero/cloudzero-costformation/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Cloudzero/cloudzero-costformation)](./LICENSE)

A Python library for defining CostFormation dimensions as classes and generating production-ready YAML output.

Full reference documentation for every class lives in [`docs/`](./docs/README.md).

## Features

### Condition Operators

**Logical:**
- `And` / `Or` — Logical operators with overloading support (`&`, `|`)
- `Not` — Logical negation

**String Comparison:**
- `Equals` — Equality matching (single value or list)
- `Contains` — Substring or list membership
- `BeginsWith` — Prefix matching
- `EndsWith` — Suffix matching
- `Matches` — Regular expression matching

**Value Checking:**
- `HasValue` — Check if dimension has a value

**Alphabetical Comparison:**
- `Before` / `BeforeOrEquals` — Less than (or equal) alphabetically
- `After` / `AfterOrEquals` — Greater than (or equal) alphabetically

**Date:**
- `ForDateRange` — Check if data exists in a date range

### Dimension Types

- `CoreDimension` — Cloud provider primitives (Account, Service, Region, etc.)
  - Class names with underscores convert to colons (e.g. `K8s_Cluster` → `K8s:Cluster`)
  - Cannot be serialized to YAML (only referenced)
- `GlobalDimension` — CloudZero-managed dimensions (`CZ:Defined:` prefix)
  - Cannot be serialized to YAML (only referenced)
  - Inherits from `CoreDimension`
- `GroupDimension` — User-defined grouping dimensions
- `AllocationDimension` — Telemetry and proportional allocations

### Dimension Attributes

- `name` — Display name (defaults to class name)
- `source` — Source dimension(s), single or list
- `rules` — List of `GroupRule`, `GroupByRule`, or `MetadataRule` objects
- `transforms` — Dimension-level transforms applied before rules
- `default_value` — Fallback when no rules match
- `child` — Hierarchical dimension relationships
- `override` — Override another dimension
- `hide` — Hide from UI
- `disable` — Disable dimension from processing

### Rule Types

- `GroupRule` — Static grouping with conditions, optional rule-level source (overrides dimension source)
- `GroupByRule` — Dynamic grouping based on source values; supports transforms, conditions, and plural sources with `CoalesceSources` for fallback logic
- `MetadataRule` — Pattern matching with substring search; supports hierarchical value patterns and optional format string for output

### Transforms

- `Lower`, `Upper`, `Title` — Case conversion
- `Split` — Split by delimiter and extract index (optional `maxsplit`)
- `Trim` — Remove leading/trailing whitespace
- `Clean` — Remove whitespace and convert special chars to dashes
- `Normalize` — Combined lowercase + whitespace removal + normalization

### Allocations

- Telemetry — `AllocateByStreams` with stream names
- Rule-based — `AllocateByRules` with an `AllocationMethod` of `Proportional` or `Even`

## Usage

Install the library from [PyPI](https://pypi.org/project/cloudzero-costformation/) with [uv](https://docs.astral.sh/uv/):

```bash
uv add cloudzero-costformation
```

Or with pip:

```bash
pip install cloudzero-costformation
```

The package installs as `cloudzero-costformation`; the import name is `costformation`.

### Core & Global Dimensions

The library includes all core cloud provider, Kubernetes, and CloudZero-managed global dimensions from the [official CFDL specification](https://docs.cloudzero.com/docs/cfdl-reference):

```python
from costformation import (
    # Core cloud provider dimensions
    Account, Service, Region, Operation, UsageType,
    CloudProvider, Resource,
    # Kubernetes dimensions
    Tag, K8s_Cluster, K8s_Namespace, K8s_Workload, K8s_Label,
    # Global dimensions (CloudZero-managed)
    ServiceDisplay, ResourceType, Category, InstanceType,
)
```

Core and global dimensions are **never defined** in CostFormation YAML, only referenced. Attempting to serialize them will raise a `TypeError`.

**Cloud Provider Dimensions:**
`Account`, `BillingConnectionID`, `CloudProvider`, `CommittedUseSubscription`, `Description`, `InvoiceID`, `LineItemType`, `Operation`, `PayerAccount`, `PricingTerm`, `PricingUnit`, `PricingUnits`, `ProductFamily`, `Region`, `Resource`, `RequestType`, `Service`, `TransferType`, `UsageDay`, `UsageFamily`, `UsageType`

**Kubernetes Dimensions:**
`K8s_Cluster`, `K8s_Namespace`, `K8s_Workload`

**Dynamic Dimensions:**
- `Tag(key)` — Cloud resource tags with any key, e.g. `Tag('Environment')`, `Tag('aws:cloudformation:stack-name')`
- `K8s_Label(name)` — Kubernetes labels with any name, e.g. `K8s_Label('app')`, `K8s_Label('node:instance-type')`

**Global Dimensions (CloudZero-managed):**
`BillingLineItem`, `Category`, `Elasticity`, `InstanceType`, `NetworkingCategory`, `NetworkingSubCategory`, `PaymentOption`, `ResourceDisplay`, `ResourceNameOnly`, `ResourceSummaryDisplay`, `ResourceSummaryID`, `ResourceType`, `ServiceDisplay`, `ServiceDetail`, `TaggableVsUntaggable`

### Basic Example

```python
from costformation import (
    Service,
    GroupDimension,
    GroupRule,
    Equals,
)

class MyServices(GroupDimension):
    name = 'My Services'
    source = Service()
    default_value = 'Other'
    rules = [
        GroupRule(
            name='Compute',
            condition=Equals(['EC2', 'Lambda', 'ECS'])
        ),
        GroupRule(
            name='Storage',
            condition=Equals(['S3', 'EBS'])
        ),
    ]

dimension = MyServices()
yaml_dict = dimension.to_dict()
```

**Output:**
```json
{
  "Name": "My Services",
  "Type": "Group",
  "Source": "Service",
  "Rules": [
    {
      "Type": "Group",
      "Name": "Compute",
      "Conditions": [{"Equals": ["EC2", "Lambda", "ECS"]}]
    },
    {
      "Type": "Group",
      "Name": "Storage",
      "Conditions": [{"Equals": ["S3", "EBS"]}]
    }
  ],
  "DefaultValue": "Other"
}
```

### Operator Overloading

```python
from costformation import (
    Category,
    Contains,
    GroupDimension,
    GroupRule,
    Lower,
    Operation,
)

class AI_Operations(GroupDimension):
    name = 'AI Operations'
    source = Operation()
    transforms = [Lower()]
    default_value = 'Non-AI'
    rules = [
        GroupRule(
            name='Input',
            condition=(
                Category().equals('AI') &
                Contains(['input', 'prompt'])
            )
        ),
    ]
```

### No Top-Level Source

```python
class ResourceName(GroupDimension):
    name = 'Resource Name'
    source = None
    override = ResourceNameOnly()
    rules = [
        GroupByRule(
            source=ResourceDisplay(),
            conditions=[Not(BeginsWith('billingitem-'))]
        ),
    ]
```

### Rule-Level Source

```python
# CustomerNames_Allocation and Customer are user-defined dimensions
# (definitions omitted for brevity)
class Customer_Names(GroupDimension):
    name = 'Customer Names'
    source = None
    rules = [
        GroupByRule(source=CustomerNames_Allocation()),
        GroupRule(
            name='CloudZero',
            source=Customer(),
            condition=Equals('00000000-0000-0000-0000-000000000000')
        ),
    ]
```

### Allocation Dimensions

```python
class AI_Telemetry(AllocationDimension):
    name = 'AI Telemetry'
    hide = True
    streams = ['cost-per-ai-call', 'ai-token-metrics']

class RuleBasedAlloc(AllocationDimension):
    name = 'Rule-based Allocation'
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = [Service().equals('AmazonEC2')]
    across_elements = [
        GroupRule(name='by-account', condition=Account().begins_with('prod-')),
    ]
```

### Evaluation

Dimensions can be evaluated against test data:

```python
test_data = {
    'Service': 'Lambda',
    'Category': 'AI',
    'Operation': 'RunInput'
}

result = MyServices.evaluate(test_data)
# Returns: 'Compute' (matches the Lambda rule)
```

## Development

### Dependency Management

#### Set up a development environment

With [uv](https://docs.astral.sh/uv/) installed, create the virtual environment at `./.venv` and install all dependencies with:

```shell
make init
```

There's no need to activate the environment — `uv run` and the make targets below use it automatically. To pin a specific Python version, run `uv venv -p 3.12 ./.venv` first.

#### Updating Dependencies

We `uv lock` requested dependencies from the `pyproject.toml` file into a deterministic `uv.lock` file.
For more information about managing dependencies with uv, see [the official docs](https://docs.astral.sh/uv/concepts/projects/dependencies/).

**Library Dependencies**

These are dependencies your library needs when a client installs it.
If you want to edit library dependencies, simply edit the `project.dependencies` value in `pyproject.toml`, or use the `uv add` command to do it for you, eg. `uv add "pydantic~=2.0"`.

**Development Dependencies**

Development dependencies are dependencies needed for development only, eg tests or linting.
If you want to edit development dependencies, then add the dependency to the appropriate `dependency-group` in `pyproject.toml`.
Alternatively, you can use `uv add` to edit the file for you eg, run `uv add --group lint ruff`.

**Locking Dependencies**

Whenever you update dependencies, you should be sure to run `make lock-requirements` in order to ensure reproducible development environments.
Whenever dependencies are updated, make sure to run `make init` to sync your virtual environment.

### Checks

#### Linting

You can run all the python linting (mypy, ruff) with:

```shell
make lint
```

Then auto-fix linting errors with:

```shell
make lint-fix
```

#### Unit Tests

You can run all the python tests with `pytest`:

```shell
make test
```

#### Full Validation

You can run both linting and testing with:

```shell
make check
```

### Publishing new versions of the package

Publishing to [PyPI](https://pypi.org/project/cloudzero-costformation/) is done by the `publish-to-pypi.yml` workflow (using [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)) whenever a GitHub Release is published:

1. Open a PR that bumps `__version__` in `costformation/__init__.py` and adds a matching section to `CHANGELOG.md` (CI enforces both).
2. Merge it, then create a GitHub Release from `main` with a tag matching the new version.
3. The workflow builds the package with uv and publishes it to PyPI.

## License

This project is licensed under the Apache License, Version 2.0 — see the
[LICENSE](./LICENSE) file for details.

## Trademarks

"CloudZero" and the CloudZero logo are trademarks of CloudZero, Inc. Use of
these trademarks is limited to identification and attribution as required by
the Apache License. You may not use CloudZero trademarks in a way that
suggests endorsement or affiliation without written permission.
