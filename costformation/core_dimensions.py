# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Predefined Core Cloud Provider Dimensions

Core dimensions are cloud provider primitives that exist at the root level of any CostFormation file.
They are never defined in CostFormation YAML, only referenced.

Source: https://docs.cloudzero.com/docs/cfdl-reference#core-cloud-provider-dimensions

Usage:
    from costformation.core_dimensions import Account, Service, Region, Tag

    class MyDimension(GroupDimension):
        source = Service()
        rules = [...]

    # Tag dimensions require a tag key
    class MyTagDimension(GroupDimension):
        source = Tag('Environment')
        rules = [...]
"""

from costformation.dimensions import CoreDimension


class Tag(CoreDimension):
    """Tag dimension with dynamic tag key

    Unlike other core dimensions, Tag requires a tag key argument.
    The dimension ID will be Tag:<key> where <key> is the tag key.

    Tag keys can be any arbitrary string.

    Usage:
        Tag('Environment')                      # Simple tag
        Tag('application')                      # Lowercase tag
        Tag('aws:cloudformation:stack-name')    # AWS-managed tag with colons
    """

    def __init__(self, key: str):
        self.key = key

    def get_id(self) -> str:
        return f'Tag:{self.key}'


class K8s_Label(CoreDimension):
    """Kubernetes label dimension with dynamic label name

    Similar to Tag, K8s_Label requires a label name argument.
    The dimension ID will be K8s:Label:<name> where <name> is the label name.

    Supports pod labels, annotations, and resource-type-specific labels across
    deployments, StatefulSets, DaemonSets, Jobs, CronJobs, Nodes, and Namespaces.

    Usage:
        K8s_Label('app')                        # Pod label
        K8s_Label('environment')                # Pod label
        K8s_Label('node:instance-type')         # Node label with resource prefix
    """

    def __init__(self, label_name: str):
        self.label_name = label_name

    def get_id(self) -> str:
        return f'K8s:Label:{self.label_name}'


class K8s_Cluster(CoreDimension):
    """Kubernetes cluster names"""


class K8s_Namespace(CoreDimension):
    """Kubernetes namespace across all clusters"""


class K8s_Workload(CoreDimension):
    """Deployed workload resources in Kubernetes clusters"""


class Account(CoreDimension):
    """IDs for any cloud account you have connected to CloudZero"""


class BillingConnectionID(CoreDimension):
    """Corresponding ID that ties back to the Billing Connection"""


class CloudProvider(CoreDimension):
    """Cloud providers supported by CloudZero (for example: AWS, GCP)"""


class CommittedUseSubscription(CoreDimension):
    """Details of specific committed use subscription or plan: RI, Savings Plan"""


class Description(CoreDimension):
    """Detailed text field that explains the specific service, resource, or pricing component"""


class InvoiceID(CoreDimension):
    """Corresponding invoice ID of the charges"""


class LineItemType(CoreDimension):
    """Type of charge for a given billing line item"""


class Operation(CoreDimension):
    """Specific cloud provider operation covered by the billing line item"""


class PayerAccount(CoreDimension):
    """Management Account associated with the charges"""


class PricingTerm(CoreDimension):
    """How charges are priced (for example: on-demand, reserved)"""


class PricingUnit(CoreDimension):
    """Unit of measurement used for billing purposes"""


class PricingUnits(CoreDimension):
    """Unit of measure used for pricing cloud resources (for example, GB, hours, requests)"""


class ProductFamily(CoreDimension):
    """Product family that the resource is associated with"""


class Region(CoreDimension):
    """Cloud region where the billed resource is located"""


class Resource(CoreDimension):
    """CloudZero Resource Name (CZRN)—unique identifier from cloud provider metadata"""


class RequestType(CoreDimension):
    """Incoming request type, such as from AWS CloudFront"""


class Service(CoreDimension):
    """Codes for the cloud provider service type"""


class TransferType(CoreDimension):
    """Type of data transfer (for example: outbound, intra-region)"""


class UsageDay(CoreDimension):
    """ISO-formatted date for the day applied to each line item"""


class UsageFamily(CoreDimension):
    """Cloud service charges"""


class UsageType(CoreDimension):
    """Usage details of the billing line item in the cloud provider"""


# Export all core dimensions
__all__ = [
    'Tag',
    'K8s_Label',
    'K8s_Cluster',
    'K8s_Namespace',
    'K8s_Workload',
    'Account',
    'BillingConnectionID',
    'CloudProvider',
    'CommittedUseSubscription',
    'Description',
    'InvoiceID',
    'LineItemType',
    'Operation',
    'PayerAccount',
    'PricingTerm',
    'PricingUnit',
    'PricingUnits',
    'ProductFamily',
    'Region',
    'Resource',
    'RequestType',
    'Service',
    'TransferType',
    'UsageDay',
    'UsageFamily',
    'UsageType',
]
