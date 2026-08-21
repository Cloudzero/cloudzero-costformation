# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Optional, TypeVar, Union

from costformation.transforms import Split

if TYPE_CHECKING:
    from costformation.dimensions import Dimension
    from costformation.transforms import Transform


T = TypeVar('T')


class Condition(ABC):
    """Base class for all conditions with operator overloading support"""

    def __and__(self, other: 'Condition') -> 'And':
        return And(self, other)

    def __or__(self, other: 'Condition') -> 'Or':
        return Or(self, other)

    def __invert__(self) -> 'Not':
        return Not(self)

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert condition to YAML-ready dictionary"""

    @abstractmethod
    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        """Evaluate condition against test data"""

    def get_dependencies(self) -> list['Dimension']:
        """Return Dimension instances this condition reads during evaluation."""
        return []

    def to_conditions_list(self) -> list[dict[str, Any]]:
        """Serialize as the body of a CFDL ``Conditions:`` list.

        Default wraps the condition in a single-element list. ``Or`` overrides to
        flatten its children — a top-level ``Or`` under ``Conditions:`` is
        represented as the implicit-OR list form rather than a nested ``Or:`` block.
        """
        return [self.to_dict()]


class _ValueCondition(Condition, Generic[T]):
    """Base for conditions carrying a value, an optional source, and transforms.

    Provides the shared ``__init__`` validation and ``to_dict`` serialization.
    Subclasses must define ``_yaml_key`` and implement ``evaluate``.
    """

    _yaml_key: ClassVar[str]

    def __init__(
        self,
        value: T,
        source: Optional['Dimension'] = None,
        sources: list['Dimension'] | None = None,
        transforms: list['Transform'] | None = None,
    ):
        if source is not None and sources is not None:
            raise ValueError('Cannot specify both source and sources')
        self.value: T = value
        self.source = source
        self.sources = sources
        self.transforms = transforms

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {self._yaml_key: self.value}
        if self.sources:
            if len(self.sources) == 1:
                result['Sources'] = self.sources[0].get_reference()
            else:
                result['Sources'] = [s.get_reference() for s in self.sources]
        elif self.source:
            result['Source'] = self.source.get_reference()
        if self.transforms:
            result['Transforms'] = [t.to_dict() for t in self.transforms]
        return result

    def get_dependencies(self) -> list['Dimension']:
        refs: list[Dimension] = []
        if self.source is not None:
            refs.append(self.source)
        if self.sources:
            refs.extend(self.sources)
        return refs

    def _apply_transforms(self, value: str) -> str | None:
        """Apply ``self.transforms`` to ``value`` in order.

        Mirrors production CFDL: condition-level transforms wrap the source
        ref before the comparison. A :class:`Split` whose index lands out of
        range produces ``''``; production wraps that in ``NULLIF(..., '')``,
        making the result NULL. We model that by returning ``None`` once any
        Split in the chain produces ``''`` — subsequent transforms are not
        applied (NULL propagates through ``LOWER`` etc. in Snowflake).
        """
        if not self.transforms:
            return value
        for t in self.transforms:
            value = t.apply(value)
            if isinstance(t, Split) and value == '':
                return None
        return value


class _SourcedCondition(_ValueCondition[T]):
    """Value-carrying condition whose ``evaluate`` resolves a single source,
    short-circuits to False on a missing dimension, and delegates comparison
    to ``_matches``.

    Not appropriate for conditions whose semantics depend on a missing value
    (see ``HasValue``).

    **String coercion.** Production CFDL emits every literal as a SQL string
    and compares it against string-typed partition columns. So a YAML scalar parsed
    as ``int`` (e.g. an unquoted account ID like ``123456789012``) still
    compares as a string in production. We coerce ``self.value`` and the
    runtime data value to ``str`` here so ``_matches`` always compares
    string-to-string.
    """

    def __init__(
        self,
        value: T,
        source: Optional['Dimension'] = None,
        sources: list['Dimension'] | None = None,
        transforms: list['Transform'] | None = None,
    ):
        coerced = [str(v) for v in value] if isinstance(value, list) else str(value)
        super().__init__(coerced, source=source, sources=sources, transforms=transforms)  # type: ignore[arg-type]

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        if self.sources:
            for s in self.sources:
                v = data.get(s.get_id())
                if v is None:
                    continue
                transformed = self._apply_transforms(str(v))
                if transformed is None:
                    continue
                if self._matches(transformed):
                    return True
            return False
        actual_source = self.source or source
        if actual_source is None:
            raise ValueError(f'{self._yaml_key} requires a source dimension for evaluation')
        actual_value = data.get(actual_source.get_id())
        if actual_value is None:
            return False
        transformed = self._apply_transforms(str(actual_value))
        if transformed is None:
            return False
        return self._matches(transformed)

    @abstractmethod
    def _matches(self, actual_value: str) -> bool:
        """Return True if ``actual_value`` (guaranteed non-None str) satisfies the condition."""


class And(Condition):
    """Logical AND condition

    Supports 1+ conditions with variable arguments. Nested ``And`` children are
    flattened so ``a & b & c`` (which Python's left-associative ``__and__``
    builds as ``And(And(a, b), c)``) collapses to a flat ``And(a, b, c)``.

    Usage:
        And(cond1)
        And(cond1, cond2)
        And(cond1, cond2, cond3, ...)
    """

    conditions: list[Condition]

    def __init__(self, *conditions: Condition):
        if len(conditions) < 1:
            raise ValueError('And requires at least 1 condition')
        flattened: list[Condition] = []
        for c in conditions:
            if isinstance(c, And):
                flattened.extend(c.conditions)
            else:
                flattened.append(c)
        self.conditions = flattened

    def to_dict(self) -> dict[str, Any]:
        return {'And': [c.to_dict() for c in self.conditions]}

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        return all(c.evaluate(data, source) for c in self.conditions)

    def get_dependencies(self) -> list['Dimension']:
        return [d for c in self.conditions for d in c.get_dependencies()]


class Or(Condition):
    """Logical OR condition

    Supports 1+ conditions with variable arguments. Nested ``Or`` children are
    flattened so ``a | b | c`` collapses to a flat ``Or(a, b, c)`` rather than
    the binary-associative ``Or(Or(a, b), c)``.

    Usage:
        Or(cond1)
        Or(cond1, cond2)
        Or(cond1, cond2, cond3, ...)
    """

    conditions: list[Condition]

    def __init__(self, *conditions: Condition):
        if len(conditions) < 1:
            raise ValueError('Or requires at least 1 condition')
        flattened: list[Condition] = []
        for c in conditions:
            if isinstance(c, Or):
                flattened.extend(c.conditions)
            else:
                flattened.append(c)
        self.conditions = flattened

    def to_dict(self) -> dict[str, Any]:
        return {'Or': [c.to_dict() for c in self.conditions]}

    def to_conditions_list(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.conditions]

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        return any(c.evaluate(data, source) for c in self.conditions)

    def get_dependencies(self) -> list['Dimension']:
        return [d for c in self.conditions for d in c.get_dependencies()]


class Not(Condition):
    """Logical negation of a condition

    Usage:
    - Not(BeginsWith('prefix'))
    - Not(Contains('substring', source=dim))
    """

    def __init__(self, condition: Condition):
        self.condition = condition

    def to_dict(self) -> dict[str, Any]:
        return {'Not': [self.condition.to_dict()]}

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        return not self.condition.evaluate(data, source)

    def get_dependencies(self) -> list['Dimension']:
        return self.condition.get_dependencies()


class Equals(_SourcedCondition[Union[str, list[str]]]):
    """Equality condition with optional source dimension

    Supports both single value and list of values:
    - Equals('value', source=dim) - checks if dimension equals 'value'
    - Equals(['val1', 'val2'], source=dim) - checks if dimension equals any value in list
    - Equals('value') - uses rule/dimension's default source
    """

    _yaml_key = 'Equals'

    def _matches(self, actual_value: str) -> bool:
        if isinstance(self.value, list):
            return actual_value in self.value
        return actual_value == self.value


class Contains(_SourcedCondition[Union[str, list[str]]]):
    """Check if dimension value contains substring or matches any value in list

    Supports:
    - Contains('substring', source=dim)
    - Contains(['val1', 'val2'], source=dim)
    - Contains('substring') - uses rule's default source (sourceless form)
    """

    _yaml_key = 'Contains'

    def _matches(self, actual_value: str) -> bool:
        if isinstance(self.value, list):
            return any(substring in actual_value for substring in self.value)
        return self.value in actual_value


class BeginsWith(_SourcedCondition[Union[str, list[str]]]):
    """Check if dimension value starts with prefix (single value or any of a list)"""

    _yaml_key = 'BeginsWith'

    def _matches(self, actual_value: str) -> bool:
        if isinstance(self.value, list):
            return any(actual_value.startswith(prefix) for prefix in self.value)
        return actual_value.startswith(self.value)


class EndsWith(_SourcedCondition[Union[str, list[str]]]):
    """Check if dimension value ends with suffix (single value or any of a list)"""

    _yaml_key = 'EndsWith'

    def _matches(self, actual_value: str) -> bool:
        if isinstance(self.value, list):
            return any(actual_value.endswith(suffix) for suffix in self.value)
        return actual_value.endswith(self.value)


_POSIX_CLASS_EQUIVALENTS = {
    'alpha': 'A-Za-z',
    'alnum': 'A-Za-z0-9',
    'digit': '0-9',
    'upper': 'A-Z',
    'lower': 'a-z',
    'space': ' \t\n\r\f\v',
    'blank': ' \t',
    'xdigit': '0-9A-Fa-f',
    'punct': '!-/:-@\\[-`{-~',
    'cntrl': '\\x00-\\x1f\\x7f',
    'print': '\\x20-\\x7e',
    'graph': '\\x21-\\x7e',
}

_POSIX_CLASS_PATTERN = re.compile(r'\[:([a-z]+):\]')

# Python-regex constructs Snowflake does NOT support (or accepts but ignores).
# Each entry: (regex to find, human-readable name shown in the error).
_UNSUPPORTED_CONSTRUCTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'\(\?='), 'lookahead (?=...)'),
    (re.compile(r'\(\?!'), 'negative lookahead (?!...)'),
    (re.compile(r'\(\?<='), 'lookbehind (?<=...)'),
    (re.compile(r'\(\?<!'), 'negative lookbehind (?<!...)'),
    (re.compile(r'\(\?P<'), 'named group (?P<name>...)'),
    (re.compile(r'\(\?P='), 'named backreference (?P=name)'),
    (re.compile(r'\(\?#'), 'inline comment (?#...)'),
    (re.compile(r'\(\?[aiLmsux]+[-:)]'), 'inline flags (?i), (?s), etc.'),
    (re.compile(r'(?<!\\)\\[1-9]'), 'backreference \\1 - \\9'),
    (re.compile(r'(?<!\\)[*+?}]\?'), 'non-greedy quantifier *?, +?, ??, }?'),
]


def _translate_posix_classes(pattern: str) -> str:
    """Replace POSIX bracket classes (``[:alpha:]`` etc.) with ASCII-equivalent
    character-class contents, because Python's ``re`` module does not support
    them and would silently mis-parse them as a character set of punctuation."""

    def sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in _POSIX_CLASS_EQUIVALENTS:
            raise ValueError(f"Unknown POSIX character class '[:{name}:]' in pattern")
        return _POSIX_CLASS_EQUIVALENTS[name]

    return _POSIX_CLASS_PATTERN.sub(sub, pattern)


def _reject_python_only_constructs(pattern: str) -> None:
    """Raise if the pattern uses any Python-regex construct Snowflake cannot
    evaluate (lookarounds, named groups, inline flags, backreferences,
    non-greedy quantifiers). Catches misuse at construction time rather than
    silently passing local evaluation and failing in production."""
    for regex, name in _UNSUPPORTED_CONSTRUCTS:
        if regex.search(pattern):
            raise ValueError(f"Matches pattern uses {name}, which Snowflake's RLIKE does not support")


class Matches(_SourcedCondition[str]):
    """Check if the dimension value matches a regular expression.

    Evaluation mirrors Snowflake's default ``RLIKE``:

    - **Full-string match** (Snowflake implicitly anchors; we use ``re.fullmatch``).
    - **Case-sensitive** and single-line (``.`` does not match newline).
    - **ASCII-only** shorthand classes (``\\d``, ``\\w``, ``\\s``) — Snowflake treats
      these as POSIX ASCII, so a fullwidth digit like ``'５'`` does not match ``\\d``.
    - **POSIX bracket classes** (``[[:alpha:]]``, ``[[:digit:]]``, ...) are translated
      to their ASCII equivalents.

    Patterns using Python-only regex features (lookarounds, named groups, inline
    flags, backreferences, non-greedy quantifiers) are rejected at construction
    time because they either error in Snowflake or silently produce different
    results.
    """

    _yaml_key = 'Matches'

    def __init__(
        self,
        pattern: str,
        source: Optional['Dimension'] = None,
        sources: list['Dimension'] | None = None,
        transforms: list['Transform'] | None = None,
    ):
        super().__init__(pattern, source=source, sources=sources, transforms=transforms)
        _reject_python_only_constructs(pattern)
        self._compiled_pattern = re.compile(_translate_posix_classes(pattern), re.ASCII)

    @property
    def pattern(self) -> str:
        return self.value

    def _matches(self, actual_value: str) -> bool:
        return self._compiled_pattern.fullmatch(actual_value) is not None


class Before(_SourcedCondition[str]):
    """Check if dimension value comes before ``value`` alphabetically (strict)"""

    _yaml_key = 'Before'

    def _matches(self, actual_value: str) -> bool:
        return actual_value < self.value


class BeforeOrEquals(_SourcedCondition[str]):
    """Check if dimension value comes before or equals ``value`` alphabetically"""

    _yaml_key = 'BeforeOrEquals'

    def _matches(self, actual_value: str) -> bool:
        return actual_value <= self.value


class After(_SourcedCondition[str]):
    """Check if dimension value comes after ``value`` alphabetically (strict)"""

    _yaml_key = 'After'

    def _matches(self, actual_value: str) -> bool:
        return actual_value > self.value


class AfterOrEquals(_SourcedCondition[str]):
    """Check if dimension value comes after or equals ``value`` alphabetically"""

    _yaml_key = 'AfterOrEquals'

    def _matches(self, actual_value: str) -> bool:
        return actual_value >= self.value


class HasValue(_ValueCondition[bool]):
    """Check if dimension has a non-null, non-empty value

    Usage:
    - HasValue(True, source=dim) - check if dimension has a value
    - HasValue(False, source=dim) - check if dimension does NOT have a value
    - HasValue(source=dim) - defaults to True
    - HasValue(True, sources=[dim1, dim2]) - check if ANY dimension has a value (OR logic)
    - HasValue() - sourceless form using rule's default source (defaults to True)
    """

    _yaml_key = 'HasValue'

    def __init__(
        self,
        value: bool = True,
        source: Optional['Dimension'] = None,
        sources: list['Dimension'] | None = None,
        transforms: list['Transform'] | None = None,
    ):
        super().__init__(value, source=source, sources=sources, transforms=transforms)

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        if self.sources:
            has_val = any(self._resolved_has_value(data.get(s.get_id())) for s in self.sources)
        else:
            actual_source = self.source or source
            if actual_source is None:
                raise ValueError('HasValue requires a source dimension for evaluation')
            has_val = self._resolved_has_value(data.get(actual_source.get_id()))
        return has_val if self.value else not has_val

    def _resolved_has_value(self, actual_value: Any) -> bool:
        """Apply self.transforms (if any), then check production ``IS NOT NULL`` semantics."""
        if actual_value is None:
            return False
        return self._apply_transforms(str(actual_value)) is not None


class ForDateRange(Condition):
    """Check whether the row's ``UsageDay`` is within a date range (inclusive).

    Production CFDL unpacks ``ForDateRange: {From: x, Until: y}`` into
    ``Between: [x, y]`` on ``Source: UsageDay``, which in turn compiles to
    ``AND(AfterOrEquals(UsageDay, x), BeforeOrEquals(UsageDay, y))``. We mirror
    that here: ``evaluate`` reads ``UsageDay`` from ``data`` and returns
    ``from_date <= UsageDay <= until_date``.

    Usage:
        ForDateRange(from_date='2025-01-01', until_date='2025-12-31')
    """

    def __init__(self, from_date: str, until_date: str):
        # ``from`` is a Python reserved word, so we use ``from_date`` / ``until_date``
        # but emit the CFDL-validator-expected ``From`` / ``Until`` YAML keys.
        self.from_date = from_date
        self.until_date = until_date

    def to_dict(self) -> dict[str, Any]:
        return {'ForDateRange': {'From': self.from_date, 'Until': self.until_date}}

    def evaluate(self, data: dict[str, Any], source: Optional['Dimension'] = None) -> bool:
        if not self.from_date or not self.until_date:
            return False
        usage_day = data.get('UsageDay')
        if usage_day is None:
            return False
        return bool(self.from_date <= usage_day <= self.until_date)

    def get_dependencies(self) -> list['Dimension']:
        # Local import avoids a circular costformation.conditions ↔ core_dimensions cycle.
        from costformation.core_dimensions import UsageDay

        return [UsageDay()]
