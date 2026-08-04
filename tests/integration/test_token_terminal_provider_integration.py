"""Integration tests for the Token Terminal provider."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from metrics.network import Network, NetworkMetricType
from metrics.overview import Overview, OverviewMetricType
from metrics.stablecoin import Stablecoin, StablecoinMetricType
from providers.token_terminal import TokenTerminal

load_dotenv()
API_KEY = os.environ.get("TOKEN_TERMINAL_API_KEY")


@pytest.mark.integration
def test_get_stablecoin_supply_live_api() -> None:
    """Calls Token Terminal API directly and validates response mapping."""
    if not API_KEY:
        pytest.skip(
            "Set TOKEN_TERMINAL_API_KEY to run live Token Terminal integration tests."
        )

    provider = TokenTerminal(api_key=API_KEY)
    metric = provider.get_metric(
        metric="stablecoin_supply",
        date="2025-01-01",
        chain="solana",
    )

    assert metric is not None
    assert isinstance(metric, Stablecoin)
    assert metric.metric_type == StablecoinMetricType.SUPPLY
    assert metric.value >= 0


@pytest.mark.integration
def test_get_validator_count_live_api() -> None:
    """Validator count is served on the network page and must be a positive count."""
    if not API_KEY:
        pytest.skip(
            "Set TOKEN_TERMINAL_API_KEY to run live Token Terminal integration tests."
        )

    provider = TokenTerminal(api_key=API_KEY)
    metric = provider.get_metric(
        metric="network_validator_count",
        date="2025-01-01",
        chain="solana",
    )

    assert metric is not None
    assert isinstance(metric, Network)
    assert metric.metric_type == NetworkMetricType.VALIDATOR_COUNT
    assert metric.value > 0


@pytest.mark.integration
def test_get_network_sol_price_live_api() -> None:
    """SOL price is shared between the overview and network pages."""
    if not API_KEY:
        pytest.skip(
            "Set TOKEN_TERMINAL_API_KEY to run live Token Terminal integration tests."
        )

    provider = TokenTerminal(api_key=API_KEY)
    metric = provider.get_metric(
        metric="network_sol_price",
        date="2025-01-01",
        chain="solana",
    )

    assert metric is not None
    assert isinstance(metric, Network)
    assert metric.metric_type == NetworkMetricType.SOL_PRICE
    assert metric.value > 0


@pytest.mark.integration
def test_get_fees_live_api_returns_sol() -> None:
    """Fees must come back in SOL, not the USD figure the API publishes."""
    if not API_KEY:
        pytest.skip(
            "Set TOKEN_TERMINAL_API_KEY to run live Token Terminal integration tests."
        )

    provider = TokenTerminal(api_key=API_KEY)
    metric = provider.get_metric(
        metric="overview_fees", date="2025-01-01", chain="solana"
    )

    assert metric is not None
    assert isinstance(metric, Overview)
    assert metric.metric_type == OverviewMetricType.FEES
    assert metric.unit == "SOL"
    # Daily network fees sit in the thousands to low tens of thousands of SOL. An
    # unconverted USD figure would land orders of magnitude above this ceiling.
    assert 0 < metric.value < 1_000_000


@pytest.mark.integration
def test_get_total_stake_live_api_returns_sol() -> None:
    """Total stake must come back as staked SOL, within SOL's total supply."""
    if not API_KEY:
        pytest.skip(
            "Set TOKEN_TERMINAL_API_KEY to run live Token Terminal integration tests."
        )

    provider = TokenTerminal(api_key=API_KEY)
    metric = provider.get_metric(
        metric="network_total_stake", date="2025-01-01", chain="solana"
    )

    assert metric is not None
    assert isinstance(metric, Network)
    assert metric.metric_type == NetworkMetricType.TOTAL_STAKE
    assert metric.unit == "SOL"
    # Staked SOL is a large share of supply but cannot exceed it.
    assert 100_000_000 < metric.value < 1_000_000_000
