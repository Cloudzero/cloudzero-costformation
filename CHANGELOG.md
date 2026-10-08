# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Changed
- Requires Python 3.11 or newer. Python 3.10 reaches end of life in October 2026 and is no longer tested or supported.
- `AllocationMethod`, `Granularity` and `CostType` are now `enum.StrEnum`. `str()` and f-strings return the value (`'Proportional'`) instead of the member name (`'AllocationMethod.PROPORTIONAL'`). `.value`, equality with plain strings, and generated CFDL are unchanged.

## [0.1.0]

### Added
- Initial public release of `cloudzero-costformation`: a Python library for authoring, testing, and generating CloudZero [CostFormation](https://docs.cloudzero.com/docs/costformation-definition-language-guide) (CFDL) definitions.
- Dimensions as typed Python classes: `GroupDimension`, `AllocationDimension`, plus all core cloud provider, Kubernetes, and CloudZero-managed global dimensions for referencing.
- Rules (`GroupRule`, `GroupByRule`, `MetadataRule`), conditions with operator overloading (`&`, `|`), transforms, and telemetry/rule-based allocations.
- Local evaluation of dimensions against sample data to test rule behavior before deploying.
- Canonical YAML/dict serialization matching production CFDL semantics.
