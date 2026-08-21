# Reference

Alphabetical index of every public class in cloudzero-costformation. Click through for details, attributes, YAML output, and Python usage.

| Class | Kind | Summary |
|-------|------|---------|
| [`Account`](core-dimensions.md#account) | Core dimension | Cloud account ID |
| [`AcrossElements`](allocation-dimension.md#acrosselements--foreachelementof) | Allocation block | Selects the destination elements in `AllocateByRules` (one of rules/groups/group_by) |
| [`After`](conditions.md#after) | Condition | Lexicographic strict-after comparison |
| [`AfterOrEquals`](conditions.md#afterorequals) | Condition | Lexicographic after-or-equal comparison |
| [`AllocationDimension`](allocation-dimension.md) | Dimension base | User-defined allocation (telemetry or rule-based) |
| [`AllocationMethod`](allocation-dimension.md#allocationmethod) | Enum | Simple-form allocation method: `Proportional` or `Even` |
| [`And`](conditions.md#and) | Condition | Logical AND of one or more conditions |
| [`Before`](conditions.md#before) | Condition | Lexicographic strict-before comparison |
| [`BeforeOrEquals`](conditions.md#beforeorequals) | Condition | Lexicographic before-or-equal comparison |
| [`BeginsWith`](conditions.md#beginswith) | Condition | Prefix match (scalar or any-of-list) |
| [`BillingConnectionID`](core-dimensions.md#billingconnectionid) | Core dimension | Billing connection identifier |
| [`BillingLineItem`](global-dimensions.md#billinglineitem) | Global dimension | Line-item category (Usage, Support, ...) |
| [`Category`](global-dimensions.md#category) | Global dimension | Cloud-provider service category |
| [`Clean`](transforms.md#clean) | Transform | Strip whitespace, replace special chars with dashes |
| [`CloudProvider`](core-dimensions.md#cloudprovider) | Core dimension | Cloud vendor (AWS, GCP, ...) |
| [`CommittedUseSubscription`](core-dimensions.md#committedusesubscription) | Core dimension | RI / Savings Plan identifier |
| [`Contains`](conditions.md#contains) | Condition | Substring match (scalar or any-of-list) |
| [`CoreDimension`](core-dimensions.md) | Dimension base | Cloud-provider primitive — referenced, never defined |
| [`CostFormation`](costformation.md) | Container | Top-level formation holding a list of dimensions; emits YAML and evaluates |
| [`CostType`](allocation-dimension.md#costtype) | Enum | Cost-basis for `ProportionalMethod` (BilledCost, RealCost, ...) |
| [`Description`](core-dimensions.md#description) | Core dimension | Line-item description text |
| [`Dimension`](group-dimension.md#dimension-base-class) | Abstract base | Root of the dimension hierarchy |
| [`Elasticity`](global-dimensions.md#elasticity) | Global dimension | Storage vs. variable-cost classification |
| [`ElementCutoff`](allocation-dimension.md#elementcutoff) | Allocation block | Bucket small elements below a cumulative threshold |
| [`EndsWith`](conditions.md#endswith) | Condition | Suffix match (scalar or any-of-list) |
| [`Equals`](conditions.md#equals) | Condition | Exact match (scalar or any-of-list) |
| [`FixedRate`](allocation-dimension.md#fixedrate) | Allocation block | Rate-based modifier for telemetry streams |
| [`ForDateRange`](conditions.md#fordaterange) | Condition | Restrict billing data to a date window |
| [`ForEachElementOf`](allocation-dimension.md#acrosselements--foreachelementof) | Allocation block | Second-level partition for Proportional allocation (same shape as `AcrossElements`) |
| [`GlobalDimension`](global-dimensions.md) | Dimension base | CloudZero-managed dimension (`CZ:Defined:` prefix) |
| [`Granularity`](allocation-dimension.md#granularity) | Enum | Time granularity for `ProportionalMethod` |
| [`GroupByRule`](rules.md#groupbyrule) | Rule | Create one output group per distinct source value |
| [`GroupDimension`](group-dimension.md) | Dimension base | User-defined classified dimension |
| [`HasValue`](conditions.md#hasvalue) | Condition | Test whether a dimension's value is non-null/non-empty |
| [`InstanceType`](global-dimensions.md#instancetype) | Global dimension | Filtered UsageType by resource type/size/family |
| [`InvoiceID`](core-dimensions.md#invoiceid) | Core dimension | Invoice identifier |
| [`K8s_Cluster`](core-dimensions.md#k8s_cluster) | Core dimension | Kubernetes cluster name |
| [`K8s_Label`](core-dimensions.md#k8s_label) | Core dimension | Kubernetes label by name |
| [`K8s_Namespace`](core-dimensions.md#k8s_namespace) | Core dimension | Kubernetes namespace across clusters |
| [`K8s_Workload`](core-dimensions.md#k8s_workload) | Core dimension | Kubernetes workload (Deployment, StatefulSet, ...) |
| [`LineItemType`](core-dimensions.md#lineitemtype) | Core dimension | Type of billing charge |
| [`Lookup`](transforms.md#lookup) | Transform | Resolve a key from a serialized JSON object |
| [`Lower`](transforms.md#lower) | Transform | Convert to lowercase |
| [`Matches`](conditions.md#matches) | Condition | Regular-expression match |
| [`MetadataRule`](rules.md#metadatarule) | Rule | Hierarchical substring matching over source values |
| [`NetworkingCategory`](global-dimensions.md#networkingcategory) | Global dimension | Major network-spend category |
| [`NetworkingSubCategory`](global-dimensions.md#networkingsubcategory) | Global dimension | Networking subcategory |
| [`Normalize`](transforms.md#normalize) | Transform | Trim + lowercase + special-to-dash |
| [`Not`](conditions.md#not) | Condition | Logical negation of a condition |
| [`Operation`](core-dimensions.md#operation) | Core dimension | Cloud-provider operation on a line item |
| [`Or`](conditions.md#or) | Condition | Logical OR of one or more conditions |
| [`PayerAccount`](core-dimensions.md#payeraccount) | Core dimension | Management account |
| [`PaymentOption`](global-dimensions.md#paymentoption) | Global dimension | Payment type (Reservation, Discount, ...) |
| [`PricingTerm`](core-dimensions.md#pricingterm) | Core dimension | Pricing structure (on-demand, reserved, ...) |
| [`PricingUnit`](core-dimensions.md#pricingunit) | Core dimension | Billing unit |
| [`PricingUnits`](core-dimensions.md#pricingunits) | Core dimension | Pricing unit of measure |
| [`ProductFamily`](core-dimensions.md#productfamily) | Core dimension | Product family |
| [`ProportionalMethod`](allocation-dimension.md#proportionalmethod) | Allocation block | Advanced Proportional spec with optional Granularity and CostType |
| [`Ref`](ref.md) | Utility | Reference a dimension by literal ID without defining it |
| [`Region`](core-dimensions.md#region) | Core dimension | Cloud region |
| [`RequestType`](core-dimensions.md#requesttype) | Core dimension | Inbound request type (CloudFront, ...) |
| [`Resource`](core-dimensions.md#resource) | Core dimension | CloudZero Resource Name (CZRN) |
| [`ResourceDisplay`](global-dimensions.md#resourcedisplay) | Global dimension | Native resource IDs for UI display |
| [`ResourceNameOnly`](global-dimensions.md#resourcenameonly) | Global dimension | Deprecated — use `ResourceSummaryDisplay` |
| [`ResourceSummaryDisplay`](global-dimensions.md#resourcesummarydisplay) | Global dimension | Groups related resources, omitting instance IDs |
| [`ResourceSummaryID`](global-dimensions.md#resourcesummaryid) | Global dimension | Summary grouping using CZRNs |
| [`ResourceType`](global-dimensions.md#resourcetype) | Global dimension | Resource type per service |
| [`Rule`](rules.md#class-hierarchy) | Rule (abstract base) | Abstract base class for all rule types |
| [`GroupRule`](rules.md#grouprule) | Rule | Classify a matching row into a named group |
| [`Service`](core-dimensions.md#service) | Core dimension | Cloud-provider service code |
| [`ServiceDetail`](global-dimensions.md#servicedetail) | Global dimension | Normalized usage/operation detail |
| [`ServiceDisplay`](global-dimensions.md#servicedisplay) | Global dimension | UI-aligned service display name |
| [`SpendToAllocate`](allocation-dimension.md#spendtoallocate) | Allocation block | Selects the pool of spend to distribute in `AllocateByRules` |
| [`Split`](transforms.md#split) | Transform | Split on a delimiter, pick an index |
| [`Tag`](core-dimensions.md#tag) | Core dimension | Tag by key (e.g., `Tag('Environment')`) |
| [`TaggableVsUntaggable`](global-dimensions.md#taggablevsuntaggable) | Global dimension | Taggable vs. untaggable classification |
| [`Title`](transforms.md#title) | Transform | Convert to Title Case |
| [`TransferType`](core-dimensions.md#transfertype) | Core dimension | Data-transfer type |
| [`Trim`](transforms.md#trim) | Transform | Strip leading/trailing whitespace |
| [`Upper`](transforms.md#upper) | Transform | Convert to UPPERCASE |
| [`UsageDay`](core-dimensions.md#usageday) | Core dimension | ISO date of line-item usage |
| [`UsageFamily`](core-dimensions.md#usagefamily) | Core dimension | Cloud service charge family |
| [`UsageType`](core-dimensions.md#usagetype) | Core dimension | Usage-type detail from the cloud provider |
