# Core Dimensions

Core dimensions are cloud-provider primitives — the raw attributes that come off each billing line item. They are **referenced**, never **defined**: you cite them as sources in your `GroupDimension` / `AllocationDimension` classes. Serializing a core dimension to YAML raises `TypeError`.

CloudZero docs:
- [Core Cloud Provider Dimensions](https://docs.cloudzero.com/docs/cfdl-reference#core-cloud-provider-dimensions)
- [Tag Dimensions](https://docs.cloudzero.com/docs/cfdl-reference#tag-dimensions)
- [Kubernetes Dimensions](https://docs.cloudzero.com/docs/cfdl-reference#kubernetes-dimensions)

## How they work

Every core dimension:

- Has an ID equal to its class name, with underscores converted to colons (e.g. `K8s_Cluster` → `K8s:Cluster`).
- `get_reference()` returns the ID directly (no prefix).
- Exposes condition-builder helpers (`equals`, `contains`, `begins_with`, `ends_with`, `matches`, `has_value`, `before`, `before_or_equals`, `after`, `after_or_equals`) that produce a condition bound to this dimension as source.

Most core dimensions are zero-arg classes — just instantiate. Two (`Tag`, `K8s_Label`) take a key argument.

## Usage

```python
from costformation import Account, K8s_Label, Service, Tag

Service().equals('AmazonEC2')
Account().begins_with('prod-')
Tag('Environment').has_value()
K8s_Label('app').equals('frontend')
```

---

## Parameterized core dimensions

### `Tag`

Tag by key. Takes the tag key as a positional argument. ID format: `Tag:<key>`.

CloudZero docs: [cfdl-reference#tag-dimensions](https://docs.cloudzero.com/docs/cfdl-reference#tag-dimensions).

```python
Tag('Environment')                            # → id 'Tag:Environment'
Tag('aws:cloudformation:stack-name')          # AWS-managed tag with colons
```

### `K8s_Label`

Kubernetes label by name. ID format: `K8s:Label:<name>`.

CloudZero docs: [cfdl-reference#kubernetes-dimensions](https://docs.cloudzero.com/docs/cfdl-reference#kubernetes-dimensions).

```python
K8s_Label('app')
K8s_Label('node:instance-type')               # resource-qualified label
```

---

## Zero-arg core dimensions

All of the following take no constructor arguments. ID is the class name with underscores replaced by colons.

CloudZero reference for all: [cfdl-reference#core-cloud-provider-dimensions](https://docs.cloudzero.com/docs/cfdl-reference#core-cloud-provider-dimensions).

### `Account`

IDs for cloud accounts connected to CloudZero.

### `BillingConnectionID`

Identifier tying back to the Billing Connection.

### `CloudProvider`

Cloud vendor (e.g., `AWS`, `GCP`).

### `CommittedUseSubscription`

Identifier for RI, Savings Plan, or similar committed-use purchases.

### `Description`

Detailed text describing the service, resource, or pricing component on the line item.

### `InvoiceID`

Invoice ID for the charges.

### `K8s_Cluster`

Kubernetes cluster name. ID: `K8s:Cluster`.

### `K8s_Namespace`

Kubernetes namespace across all clusters. ID: `K8s:Namespace`.

### `K8s_Workload`

Deployed workload resource (Deployment, StatefulSet, DaemonSet, Job, CronJob, Node, Namespace). ID: `K8s:Workload`.

### `LineItemType`

Type of charge for a given billing line item.

### `Operation`

Specific cloud-provider operation covered by the line item.

### `PayerAccount`

Management account associated with the charges.

### `PricingTerm`

How charges are priced (on-demand, reserved, ...).

### `PricingUnit`

Unit of measurement used for billing purposes.

### `PricingUnits`

Unit of measure used for pricing cloud resources (GB, hours, requests, ...).

### `ProductFamily`

Product family the resource is associated with.

### `Region`

Cloud region where the billed resource is located.

### `RequestType`

Incoming request type, such as from AWS CloudFront.

### `Resource`

CloudZero Resource Name (CZRN) — a unique identifier derived from cloud-provider metadata.

### `Service`

Codes for the cloud-provider service type (e.g., `AmazonEC2`, `AWSLambda`).

### `TransferType`

Type of data transfer (outbound, intra-region, ...).

### `UsageDay`

ISO-formatted date for the day applied to each line item (e.g., `2025-04-19`).

### `UsageFamily`

Cloud-service charge family.

### `UsageType`

Usage details of the billing line item in the cloud provider.
