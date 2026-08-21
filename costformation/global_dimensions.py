# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Predefined CloudZero Global Dimensions

Global dimensions are CloudZero-managed dimensions that provide additional cloud provider insights.
They are never defined in CostFormation YAML, only referenced with the CZ:Defined: prefix.

Source: https://docs.cloudzero.com/docs/cfdl-reference#additional-cloud-provider-dimensions

Usage:
    from costformation.global_dimensions import (
        ServiceDisplay, ResourceType, Category
    )

    class MyDimension(GroupDimension):
        source = ServiceDisplay()
        rules = [...]
"""

from costformation.dimensions import GlobalDimension


class BillingLineItem(GlobalDimension):
    """Categories of billing line item (for example: Usage, Support)"""


class Category(GlobalDimension):
    """Different categories of services similar to what you would see in your cloud provider console"""


class CommittedUseSubscription_Display(GlobalDimension):
    """Display name for committed-use subscriptions (RIs, Savings Plans, etc.)"""


class Elasticity(GlobalDimension):
    """Classifies spend into two types: storage and variable costs"""


class GenAI_Model(GlobalDimension):
    """GenAI model identifier (e.g., claude-opus-4-5)"""


class GenAI_Model_Family(GlobalDimension):
    """GenAI model family (e.g., Claude)"""


class GenAI_Model_Family_Override(GlobalDimension):
    """Customer override hook for GenAI_Model_Family"""


class GenAI_Model_Override(GlobalDimension):
    """Customer override hook for GenAI_Model"""


class GenAI_Platform(GlobalDimension):
    """GenAI platform / provider (e.g., Anthropic, OpenAI, Bedrock)"""


class GenAI_Platform_Override(GlobalDimension):
    """Customer override hook for GenAI_Platform"""


class GenAI_TokenType(GlobalDimension):
    """GenAI token type (input, output, cache-read, cache-write, ...)"""


class InstanceType(GlobalDimension):
    """Grouped by a sub-section of the UsageType name and filtered to show costs related to resource type, size, and family"""


class NetworkingCategory(GlobalDimension):
    """Major types of networking spend (for example: VPC Endpoints, Data Transfer)"""


class NetworkingCategory_VPCFlowlog(GlobalDimension):
    """Networking category specialization for VPC Flow Log-derived spend"""


class NetworkingSubCategory(GlobalDimension):
    """Deeper breakdown of networking-related costs"""


class PaymentOption(GlobalDimension):
    """Different payment types (for example: Reservation, Discount) grouped based on line item and usage details"""


class ResourceDisplay(GlobalDimension):
    """Uses native resource IDs instead of CZRNs for better UI alignment"""


class ResourceNameOnly(GlobalDimension):
    """Deprecated: use ResourceSummaryDisplay instead"""


class ResourceSummaryDisplay(GlobalDimension):
    """Groups logically related resources while omitting individual instance IDs"""


class ResourceSummaryID(GlobalDimension):
    """Summary grouping using CZRNs instead of native resource IDs"""


class ResourceSummaryID_Override(GlobalDimension):
    """Customer override hook for ResourceSummaryID"""


class Resource_LowCardinality(GlobalDimension):
    """Low-cardinality alternative to Resource (aggregates chatty resources)"""


class ResourceType(GlobalDimension):
    """Resource types for each cloud provider service"""


class ResourceType_Split(GlobalDimension):
    """Split variant of ResourceType (finer-grained breakdown)"""


class ServiceCategory_Override(GlobalDimension):
    """Customer override hook for service category assignment"""


class ServiceDisplay(GlobalDimension):
    """Aligns with CloudZero UI display values for services"""


class ServiceDetail(GlobalDimension):
    """Normalized version of detailed data stored in usage and operation fields"""


class ServiceDetail_Breakdown_AWS(GlobalDimension):
    """AWS-specific breakdown of ServiceDetail"""


class ServiceDetail_Breakdown_Azure(GlobalDimension):
    """Azure-specific breakdown of ServiceDetail"""


class ServiceDetail_DT_InterRegion_AWS(GlobalDimension):
    """AWS inter-region data-transfer breakdown within ServiceDetail"""


class TaggableVsUntaggable(GlobalDimension):
    """Distinguishes taggable resources from various untaggable resource categories"""


# Export all global dimensions
__all__ = [
    'BillingLineItem',
    'Category',
    'CommittedUseSubscription_Display',
    'Elasticity',
    'GenAI_Model',
    'GenAI_Model_Family',
    'GenAI_Model_Family_Override',
    'GenAI_Model_Override',
    'GenAI_Platform',
    'GenAI_Platform_Override',
    'GenAI_TokenType',
    'InstanceType',
    'NetworkingCategory',
    'NetworkingCategory_VPCFlowlog',
    'NetworkingSubCategory',
    'PaymentOption',
    'Resource_LowCardinality',
    'ResourceDisplay',
    'ResourceNameOnly',
    'ResourceSummaryDisplay',
    'ResourceSummaryID',
    'ResourceSummaryID_Override',
    'ResourceType',
    'ResourceType_Split',
    'ServiceCategory_Override',
    'ServiceDetail',
    'ServiceDetail_Breakdown_AWS',
    'ServiceDetail_Breakdown_Azure',
    'ServiceDetail_DT_InterRegion_AWS',
    'ServiceDisplay',
    'TaggableVsUntaggable',
]
