# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""End-to-end test exercising a realistic CostFormation: serialization to YAML and
evaluation through dimensions whose source data is the output of upstream dimensions."""

import pytest

from costformation.allocations import AllocationMethod
from costformation.conditions import BeginsWith, Equals
from costformation.core_dimensions import Account, Service, Tag
from costformation.dimensions import AllocationDimension, CostFormation, GroupDimension
from costformation.rules import GroupByRule, GroupRule, MetadataRule
from costformation.transforms import Lower, Normalize

ENV_TAG = Tag('Environment')
TEAM_TAG = Tag('Team')


class Environment(GroupDimension):
    """Normalize environment from the Environment tag, falling back to account naming."""

    name = 'Environment Classification'
    source = ENV_TAG
    transforms = [Lower()]
    rules = [
        GroupRule(name='production', condition=BeginsWith('prod')),
        GroupRule(name='staging', condition=BeginsWith('stag')),
        GroupRule(name='development', condition=BeginsWith('dev') | Equals('test')),
        GroupRule(name='production', condition=Account().begins_with('prod-')),
    ]
    default_value = 'unknown'


class ServiceCategory(GroupDimension):
    """Bucket cloud services into coarse categories using hierarchical substring matching."""

    source = Service()
    rules = [
        MetadataRule(
            Service(),
            [
                {'compute': ['EC2', 'Lambda', 'Fargate']},
                {'storage': ['S3', 'EBS', 'EFS']},
                {'database': ['RDS', 'DynamoDB', 'Redshift']},
                {'network': ['CloudFront', 'Route53', 'VPC']},
            ],
        ),
    ]
    default_value = 'other'


class Team(GroupDimension):
    """Pull team name from the Team tag, normalized to a slug."""

    source = TEAM_TAG
    rules = [
        GroupByRule(
            source=TEAM_TAG,
            transforms=[Normalize()],
            conditions=[TEAM_TAG.has_value()],
        ),
    ]
    default_value = 'unowned'


class CostBucket(GroupDimension):
    """Cross-cut Environment x ServiceCategory using a precomputed upstream Environment value."""

    name = 'Cost Bucket'
    source = Environment()
    rules = [
        GroupRule(
            name='prod-compute',
            condition=Environment().equals('production') & ServiceCategory().equals('compute'),
        ),
        GroupRule(
            name='prod-storage',
            condition=Environment().equals('production') & ServiceCategory().equals('storage'),
        ),
        GroupRule(
            name='prod-database',
            condition=Environment().equals('production') & ServiceCategory().equals('database'),
        ),
        GroupRule(
            name='non-prod-compute',
            condition=(
                (Environment().equals('staging') | Environment().equals('development')) & ServiceCategory().equals('compute')
            ),
        ),
    ]
    default_value = 'uncategorized'


class TelemetryAllocation(AllocationDimension):
    name = 'Telemetry Stream Allocation'
    streams = ['cost-per-request', 'cost-per-user']


class AllocationCategory(GroupDimension):
    """Bucket the telemetry-allocated spend by which stream produced it. Depends on
    TelemetryAllocation, which has no evaluable value — the upstream allocation must
    therefore be supplied as an input when evaluating this dimension."""

    source = TelemetryAllocation()
    rules = [
        GroupRule(name='per-user', condition=TelemetryAllocation().equals('cost-per-user')),
        GroupRule(name='per-request', condition=TelemetryAllocation().equals('cost-per-request')),
    ]
    default_value = 'unbucketed'


class RuleBasedAllocation(AllocationDimension):
    allocation_method = AllocationMethod.PROPORTIONAL
    spend_to_allocate = [Service().equals('AmazonEC2')]
    across_elements = [GroupRule(name='high-cost-account', condition=Account().begins_with('prod-'))]


COSTFORMATION = CostFormation(
    [
        Environment(),
        ServiceCategory(),
        Team(),
        CostBucket(),
        TelemetryAllocation(),
        AllocationCategory(),
        RuleBasedAllocation(),
    ]
)


# Snapshot of COSTFORMATION.to_yaml() — regenerate with:
#     python -c "from tests.test_end_to_end import COSTFORMATION; print(COSTFORMATION.to_yaml())"
EXPECTED_YAML = """\
Dimensions:
  Environment:
    Name: Environment Classification
    Source: Tag:Environment
    Transforms:
    - Type: Lower
    Rules:
    - Type: Group
      Name: production
      Conditions:
      - BeginsWith: prod
    - Type: Group
      Name: staging
      Conditions:
      - BeginsWith: stag
    - Type: Group
      Name: development
      Conditions:
      - BeginsWith: dev
      - Equals: test
    - Type: Group
      Name: production
      Conditions:
      - BeginsWith: prod-
        Source: Account
    DefaultValue: unknown
  ServiceCategory:
    Source: Service
    Rules:
    - Type: Metadata
      Source: Service
      Values:
      - compute:
        - EC2
        - Lambda
        - Fargate
      - storage:
        - S3
        - EBS
        - EFS
      - database:
        - RDS
        - DynamoDB
        - Redshift
      - network:
        - CloudFront
        - Route53
        - VPC
    DefaultValue: other
  Team:
    Source: Tag:Team
    Rules:
    - Type: GroupBy
      Source: Tag:Team
      Transforms:
      - Type: Normalize
      Conditions:
      - HasValue: true
        Source: Tag:Team
    DefaultValue: unowned
  CostBucket:
    Name: Cost Bucket
    Source: User:Defined:Environment
    Rules:
    - Type: Group
      Name: prod-compute
      Conditions:
      - And:
        - Equals: production
          Source: User:Defined:Environment
        - Equals: compute
          Source: User:Defined:ServiceCategory
    - Type: Group
      Name: prod-storage
      Conditions:
      - And:
        - Equals: production
          Source: User:Defined:Environment
        - Equals: storage
          Source: User:Defined:ServiceCategory
    - Type: Group
      Name: prod-database
      Conditions:
      - And:
        - Equals: production
          Source: User:Defined:Environment
        - Equals: database
          Source: User:Defined:ServiceCategory
    - Type: Group
      Name: non-prod-compute
      Conditions:
      - And:
        - Or:
          - Equals: staging
            Source: User:Defined:Environment
          - Equals: development
            Source: User:Defined:Environment
        - Equals: compute
          Source: User:Defined:ServiceCategory
    DefaultValue: uncategorized
  TelemetryAllocation:
    Type: Allocation
    Name: Telemetry Stream Allocation
    AllocateByStreams:
      Streams:
      - cost-per-request
      - cost-per-user
  AllocationCategory:
    Source: User:Defined:TelemetryAllocation
    Rules:
    - Type: Group
      Name: per-user
      Conditions:
      - Equals: cost-per-user
        Source: User:Defined:TelemetryAllocation
    - Type: Group
      Name: per-request
      Conditions:
      - Equals: cost-per-request
        Source: User:Defined:TelemetryAllocation
    DefaultValue: unbucketed
  RuleBasedAllocation:
    Type: Allocation
    AllocateByRules:
      AllocationMethod: Proportional
      SpendToAllocate:
        Conditions:
        - Equals: AmazonEC2
          Source: Service
      AcrossElements:
        Rules:
        - Type: Group
          Name: high-cost-account
          Conditions:
          - BeginsWith: prod-
            Source: Account
"""


@pytest.mark.unit
def test_complex_costformation_should_serialize_to_expected_yaml():
    assert COSTFORMATION.to_yaml() == EXPECTED_YAML


@pytest.mark.unit
@pytest.mark.parametrize(
    'input_data, expected',
    [
        pytest.param(
            {'Tag:Environment': 'PRODUCTION', 'Service': 'AmazonEC2', 'Tag:Team': 'Data Platform'},
            {
                'Environment': 'production',
                'ServiceCategory': 'compute',
                'Team': 'data-platform',
                'CostBucket': 'prod-compute',
            },
            id='prod-ec2-data-platform',
        ),
        pytest.param(
            {'Tag:Environment': 'Prod', 'Service': 'AmazonS3', 'Tag:Team': 'Web Frontend'},
            {
                'Environment': 'production',
                'ServiceCategory': 'storage',
                'Team': 'web-frontend',
                'CostBucket': 'prod-storage',
            },
            id='prod-s3-web-frontend',
        ),
        pytest.param(
            {'Tag:Environment': 'staging', 'Service': 'AWSLambda', 'Tag:Team': 'ML Ops'},
            {
                'Environment': 'staging',
                'ServiceCategory': 'compute',
                'Team': 'ml-ops',
                'CostBucket': 'non-prod-compute',
            },
            id='staging-lambda-ml-ops',
        ),
        pytest.param(
            {'Tag:Environment': 'dev', 'Service': 'AmazonRDS', 'Tag:Team': 'Backend'},
            {
                'Environment': 'development',
                'ServiceCategory': 'database',
                'Team': 'backend',
                'CostBucket': 'uncategorized',
            },
            id='dev-rds-falls-through-to-default-bucket',
        ),
        pytest.param(
            {'Tag:Environment': 'test', 'Service': 'AmazonDynamoDB'},
            {
                'Environment': 'development',
                'ServiceCategory': 'database',
                'Team': 'unowned',
                'CostBucket': 'uncategorized',
            },
            id='test-env-treated-as-development-and-team-defaults',
        ),
        pytest.param(
            {'Service': 'AmazonCloudFront', 'Account': 'prod-billing', 'Tag:Team': 'Platform'},
            {
                'Environment': 'production',
                'ServiceCategory': 'network',
                'Team': 'platform',
                'CostBucket': 'uncategorized',
            },
            id='no-env-tag-falls-back-to-account-prefix-rule',
        ),
        pytest.param(
            {'Service': 'AmazonSageMaker', 'Tag:Environment': 'prod', 'Tag:Team': 'AI Research'},
            {
                'Environment': 'production',
                'ServiceCategory': 'other',
                'Team': 'ai-research',
                'CostBucket': 'uncategorized',
            },
            id='unknown-service-buckets-to-other-and-uncategorized',
        ),
        pytest.param(
            {'Service': 'AmazonEC2'},
            {
                'Environment': 'unknown',
                'ServiceCategory': 'compute',
                'Team': 'unowned',
                'CostBucket': 'uncategorized',
            },
            id='no-tags-no-account-falls-through-all-defaults',
        ),
        pytest.param(
            {'TelemetryAllocation': 'cost-per-user'},
            {'AllocationCategory': 'per-user'},
            id='allocation-value-supplied-as-input-bypasses-allocation-evaluation',
        ),
    ],
)
def test_costformation_evaluate_should_resolve_upstream_dependencies(input_data, expected):
    for dim_id, expected_value in expected.items():
        assert COSTFORMATION.evaluate(input_data, dim_id, allow_missing_inputs=True) == expected_value
