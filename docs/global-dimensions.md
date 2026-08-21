# Global Dimensions

Global dimensions are **CloudZero-managed**: they provide additional insights derived from cloud-provider data (normalized service names, instance-type breakdowns, networking categories, ...). Like core dimensions they are **referenced, never defined** — serializing one to YAML raises `TypeError`.

CloudZero docs: [Additional Cloud Provider Dimensions](https://docs.cloudzero.com/docs/cfdl-reference#additional-cloud-provider-dimensions).

## How they work

- ID is the class name.
- `get_reference()` returns `CZ:Defined:<ClassName>` — the `CZ:Defined:` prefix is what distinguishes globals from core dimensions in YAML.
- Same condition-builder helpers as all other dimensions (`equals`, `contains`, `begins_with`, ...).

## Usage

```python
from costformation import Category, Equals, ServiceDisplay

ServiceDisplay().equals('Amazon Elastic Compute Cloud')
Category().contains('Compute')
```

```yaml
# when referenced from another dimension's condition
- Equals: Amazon Elastic Compute Cloud
  Source: CZ:Defined:ServiceDisplay
```

---

CloudZero reference for all: [cfdl-reference#additional-cloud-provider-dimensions](https://docs.cloudzero.com/docs/cfdl-reference#additional-cloud-provider-dimensions).

## `BillingLineItem`

Categories of billing line item (Usage, Support, ...).

## `Category`

Different categories of services — similar to what you'd see in the cloud-provider console.

## `Elasticity`

Classifies spend into storage vs. variable costs.

## `InstanceType`

Grouped by a sub-section of `UsageType`, filtered to show costs related to resource type, size, and family.

## `NetworkingCategory`

Major types of networking spend (VPC Endpoints, Data Transfer, ...).

## `NetworkingSubCategory`

Deeper breakdown of networking-related costs.

## `PaymentOption`

Payment types grouped based on line item and usage details (Reservation, Discount, ...).

## `ResourceDisplay`

Uses native resource IDs instead of CZRNs for better UI alignment.

## `ResourceNameOnly`

**Deprecated** — use `ResourceSummaryDisplay` instead.

## `ResourceSummaryDisplay`

Groups logically related resources while omitting individual instance IDs.

## `ResourceSummaryID`

Summary grouping using CZRNs instead of native resource IDs.

## `ResourceType`

Resource types for each cloud-provider service.

## `ServiceDetail`

Normalized version of detailed data stored in usage and operation fields.

## `ServiceDisplay`

Aligns with the CloudZero UI display values for services.

## `TaggableVsUntaggable`

Distinguishes taggable resources from various untaggable resource categories.
