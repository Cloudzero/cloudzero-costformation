# SPDX-FileCopyrightText: Copyright (c) CloudZero, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: init lint lint-fix test lock-requirements check-locks check

init:
	uv venv --allow-existing --relocatable ./.venv
	uv sync

lint:
	uv run mypy .
	uv run python -m ruff format -q --check
	uv run python -m ruff check -q

lint-fix:
	uv run python -m ruff format -q
	uv run python -m ruff check -q --fix

test:
	uv run pytest

lock-requirements:
	uv lock

check-locks:
	uv lock --check

check: lint test
