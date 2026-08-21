# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from costformation import transforms


@pytest.mark.unit
@pytest.mark.parametrize(
    'transform_cls, input_value, expected',
    [
        pytest.param(transforms.Lower, 'AmazonEC2', 'amazonec2', id='lower'),
        pytest.param(transforms.Upper, 'AmazonEC2', 'AMAZONEC2', id='upper'),
        pytest.param(transforms.Title, 'amazon ec2', 'Amazon Ec2', id='title'),
        pytest.param(transforms.Trim, '  spaced  ', 'spaced', id='trim'),
        # Production ``TRIM(input, ' \t')`` strips ONLY space and tab — newlines, carriage
        # returns, vertical tab, and form feed at the boundary are preserved.
        pytest.param(transforms.Trim, '\thello\t', 'hello', id='trim-strips-tabs'),
        pytest.param(transforms.Trim, '\nhello\n', '\nhello\n', id='trim-preserves-newlines'),
    ],
)
def test_simple_transforms_should_apply_expected_mapping(transform_cls, input_value, expected):
    assert transform_cls().apply(input_value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'transform_cls, type_name',
    [
        pytest.param(transforms.Lower, 'Lower', id='lower'),
        pytest.param(transforms.Upper, 'Upper', id='upper'),
        pytest.param(transforms.Title, 'Title', id='title'),
        pytest.param(transforms.Trim, 'Trim', id='trim'),
        pytest.param(transforms.Clean, 'Clean', id='clean'),
        pytest.param(transforms.Normalize, 'Normalize', id='normalize'),
    ],
)
def test_simple_transforms_to_dict_should_serialize_type(transform_cls, type_name):
    assert transform_cls().to_dict() == {'Type': type_name}


@pytest.mark.unit
@pytest.mark.parametrize(
    'input_value, delimiter, index, maxsplit, expected',
    [
        pytest.param('a/b/c', '/', 1, None, 'a', id='first-part'),
        pytest.param('a/b/c', '/', 3, None, 'c', id='last-part'),
        pytest.param('a/b/c', '/', 5, None, '', id='index-past-end-returns-empty'),
        pytest.param('a/b/c', '/', 0, None, 'a', id='index-zero-treated-as-one'),
        pytest.param('a/b/c', '/', -1, None, 'c', id='negative-index-counts-from-end'),
        pytest.param('a/b/c', '/', -3, None, 'a', id='negative-index-reaches-first'),
        pytest.param('a/b/c', '/', -4, None, '', id='negative-index-out-of-range-returns-empty'),
        pytest.param('a/b/c/d', '/', 2, 1, 'b/c/d', id='maxsplit-limits-splits'),
        pytest.param('no-delimiter', '/', 1, None, 'no-delimiter', id='no-delimiter-returns-whole-value'),
    ],
)
def test_split_apply_should_match_snowflake_split_part_semantics(input_value, delimiter, index, maxsplit, expected):
    assert transforms.Split(delimiter, index, maxsplit).apply(input_value) == expected


@pytest.mark.unit
def test_split_to_dict_should_include_required_fields():
    assert transforms.Split('/', 1).to_dict() == {'Type': 'Split', 'Delimiter': '/', 'Index': 1}


@pytest.mark.unit
def test_split_to_dict_should_include_maxsplit_when_set():
    assert transforms.Split('/', 1, maxsplit=2).to_dict() == {
        'Type': 'Split',
        'Delimiter': '/',
        'Index': 1,
        'Maxsplit': 2,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'input_value, expected',
    [
        pytest.param('hello world', 'hello-world', id='space-to-dash'),
        # Whitespace at the edges is translated to dashes BEFORE the strip, so the
        # dashes remain. Production: translate → '--leading-trailing--', trim
        # (whitespace only) → unchanged.
        pytest.param('  leading trailing  ', '--leading-trailing--', id='edge-whitespace-becomes-edge-dashes'),
        pytest.param('already-clean', 'already-clean', id='already-clean'),
        pytest.param('special!chars#here', 'special-chars-here', id='special-chars-to-dashes'),
        pytest.param('multiple   spaces', 'multiple---spaces', id='each-special-char-becomes-one-dash'),
        pytest.param('foo_bar', 'foo-bar', id='underscore-to-dash'),
        pytest.param('foo@bar', 'foo@bar', id='at-sign-preserved'),
        pytest.param('foo+bar?baz', 'foo+bar?baz', id='unlisted-specials-preserved'),
    ],
)
def test_clean_apply_should_translate_special_chars_to_dash(input_value, expected):
    assert transforms.Clean().apply(input_value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'key, serialized, expected',
    [
        pytest.param('foo', '{"foo": "bar"}', 'bar', id='resolves-single-key'),
        pytest.param('name', '{"name": "AmazonEC2", "id": "i-123"}', 'AmazonEC2', id='resolves-among-multiple'),
        pytest.param('id', '{"name": "AmazonEC2", "id": "i-123"}', 'i-123', id='resolves-second-key'),
    ],
)
def test_lookup_apply_should_resolve_key_from_serialized_dict(key, serialized, expected):
    assert transforms.Lookup(key).apply(serialized) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    'serialized',
    [
        pytest.param('{"other": "bar"}', id='key-absent'),
        pytest.param('{"foo": null}', id='key-present-but-null'),
        pytest.param('not-a-dict', id='not-valid-json'),
        pytest.param('["foo", "bar"]', id='json-but-not-an-object'),
        pytest.param('[' * 100_000 + ']' * 100_000, id='deeply-nested-json-recursion'),
    ],
)
def test_lookup_apply_should_return_empty_string_when_key_unresolved(serialized):
    assert transforms.Lookup('foo').apply(serialized) == ''


@pytest.mark.unit
def test_lookup_to_dict_should_serialize_type_and_key():
    assert transforms.Lookup('resource_id').to_dict() == {'Type': 'Lookup', 'Key': 'resource_id'}


@pytest.mark.unit
def test_lookup_is_exported_from_package():
    import costformation

    assert costformation.Lookup is transforms.Lookup


@pytest.mark.unit
@pytest.mark.parametrize(
    'input_value, expected',
    [
        pytest.param('Hello World', 'hello-world', id='lowercase-and-dash'),
        pytest.param('  Mixed CASE  ', '--mixed-case--', id='edge-whitespace-becomes-edge-dashes'),
        pytest.param('Already-Normal', 'already-normal', id='lowercase-existing-dashes'),
        pytest.param('Special!CHARS', 'special-chars', id='special-chars'),
        pytest.param('Foo_Bar', 'foo-bar', id='underscore-to-dash-and-lowercased'),
        pytest.param('foo@Bar', 'foo@bar', id='at-sign-preserved'),
        # `_trim` strips whitespace only — chars not in the special-set are kept
        # verbatim, including any dashes adjacent to them.
        pytest.param('a@b ', 'a@b-', id='trailing-space-becomes-trailing-dash'),
    ],
)
def test_normalize_apply_should_match_production_cfdl(input_value, expected):
    assert transforms.Normalize().apply(input_value) == expected
