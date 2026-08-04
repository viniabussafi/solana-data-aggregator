"""Unit tests for the Token Terminal provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from metrics.network import Network, NetworkMetricType
from metrics.overview import Overview, OverviewMetricType
from metrics.stablecoin import Stablecoin, StablecoinMetricType
from providers.token_terminal import TokenTerminal


def test_get_stablecoin_supply_sums_native_and_bridged() -> None:
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {
            "timestamp": "2026-01-01T00:00:00.000Z",
            "ecosystem_stablecoin_supply": 10_987_267_570.64,
            "ecosystem_bridged_stablecoin_supply": 2_500_000_000.0,
        },
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Stablecoin, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("stablecoin_supply", "2026-01-01", "solana")

    assert result is sentinel_metric
    mock_factory.assert_called_once()
    assert mock_factory.call_args.kwargs["metric_type"] == StablecoinMetricType.SUPPLY
    # Total supply = native issuance + bridged-in supply.
    assert mock_factory.call_args.kwargs["value"] == pytest.approx(13_487_267_570.64)


def test_get_stablecoin_supply_tolerates_missing_bridged_value() -> None:
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {
            "timestamp": "2026-01-01T00:00:00.000Z",
            "ecosystem_stablecoin_supply": 10_987_267_570.64,
        },
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Stablecoin, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("stablecoin_supply", "2026-01-01", "solana")

    assert result is sentinel_metric
    assert mock_factory.call_args.kwargs["value"] == 10_987_267_570.64


def test_get_validator_count_returns_network_metric() -> None:
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {"timestamp": "2026-01-01T00:00:00.000Z", "number_of_validators": 683},
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Network, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("network_validator_count", "2026-01-01", "solana")

    assert result is sentinel_metric
    assert (
        mock_factory.call_args.kwargs["metric_type"]
        == NetworkMetricType.VALIDATOR_COUNT
    )
    assert mock_factory.call_args.kwargs["value"] == 683


def test_get_network_sol_price_returns_network_metric() -> None:
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {"timestamp": "2026-01-01T00:00:00.000Z", "price": 73.45},
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Network, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("network_sol_price", "2026-01-01", "solana")

    assert result is sentinel_metric
    assert mock_factory.call_args.kwargs["metric_type"] == NetworkMetricType.SOL_PRICE
    assert mock_factory.call_args.kwargs["value"] == pytest.approx(73.45)


def test_every_supported_metric_has_a_metric_type() -> None:
    """Each entry in METRIC_MAP must resolve to a typed metric model."""
    assert set(TokenTerminal.METRIC_MAP) == set(TokenTerminal.METRIC_TYPE_MAP)


def test_get_fees_converts_usd_to_sol() -> None:
    """Fees are published in USD and reported in SOL at that day's SOL price."""
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {
            "timestamp": "2026-08-02T00:00:00.000Z",
            "fees": 423_331.0,
            "price": 73.45,
        },
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Overview, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("overview_fees", "2026-08-02", "solana")

    assert result is sentinel_metric
    assert mock_factory.call_args.kwargs["metric_type"] == OverviewMetricType.FEES
    assert mock_factory.call_args.kwargs["value"] == pytest.approx(5763.6, abs=0.1)


def test_get_total_stake_converts_usd_to_sol() -> None:
    """Staking market cap is published in USD and reported as staked SOL."""
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {
            "timestamp": "2026-08-02T00:00:00.000Z",
            "staking_market_cap": 32_608_524_558.0,
            "price": 73.45,
        },
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()
    sentinel_metric = object()

    with (
        patch.object(provider._session, "get", return_value=mock_resp),
        patch.object(
            Network, "from_metric_type", return_value=sentinel_metric
        ) as mock_factory,
    ):
        result = provider.get_metric("network_total_stake", "2026-08-02", "solana")

    assert result is sentinel_metric
    assert mock_factory.call_args.kwargs["metric_type"] == NetworkMetricType.TOTAL_STAKE
    assert mock_factory.call_args.kwargs["value"] == pytest.approx(
        443_955_411, rel=1e-6
    )


def test_ratio_metric_drops_days_without_a_price() -> None:
    """A day with no usable price cannot be converted, so it is dropped."""
    provider = TokenTerminal(api_key="test-token-terminal-key")
    mock_response = [
        {"timestamp": "2026-08-01T00:00:00.000Z", "fees": 423_994.0, "price": None},
        {"timestamp": "2026-08-02T00:00:00.000Z", "fees": 423_331.0, "price": 0},
        {"timestamp": "2026-08-03T00:00:00.000Z", "fees": 615_367.0, "price": 73.439},
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch.object(provider._session, "get", return_value=mock_resp):
        rows = provider.fetch_rows("overview_fees", "2026-08-01", "2026-08-03")

    assert [row["date"] for row in rows] == ["2026-08-03"]
    assert rows[0]["value"] == pytest.approx(8379.3, abs=0.1)
