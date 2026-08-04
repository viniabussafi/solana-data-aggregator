"""Token Terminal data provider."""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, List, Optional

import requests

from metrics.defi import Defi, DefiMetricType
from metrics.network import Network, NetworkMetricType
from metrics.overview import Overview, OverviewMetricType
from metrics.stablecoin import Stablecoin, StablecoinMetricType
from providers.base import BaseProvider


class TokenTerminal(BaseProvider):
    """Fetch metrics from the Token Terminal v2 API."""

    METRIC_MAP: Dict[str, Dict[str, Any]] = {
        "overview_tx_count_total": {
            "metric_id": "transaction_count",
            "date_field": "timestamp",
            "value_field": "transaction_count",
        },
        "overview_tx_count_vote": {
            "metric_id": "vote_transaction_count",
            "date_field": "timestamp",
            "value_field": "vote_transaction_count",
        },
        "overview_sol_price": {
            "metric_id": "price",
            "date_field": "timestamp",
            "value_field": "price",
        },
        "overview_fee_payers": {
            "metric_id": "active_addresses_daily",
            "date_field": "timestamp",
            "value_field": "active_addresses_daily",
        },
        "overview_fees": {
            # Token Terminal publishes Solana fees in USD, built by multiplying the
            # native SOL amount by that day's SOL price. Dividing the published USD
            # figure by the same published price recovers the native SOL amount.
            "metric_id": "fees,price",
            "date_field": "timestamp",
            "value_field": ["fees", "price"],
            "combine": "ratio",
            "methodology": (
                "Daily fees in SOL, taken as Token Terminal's USD fee figure divided "
                "by the same daily SOL price used to build it. Fees are the sum of "
                "each block's total fee, so base and priority fees are both included, "
                "and fees paid by vote transactions are included."
            ),
        },
        "stablecoin_supply": {
            # Total stablecoin supply = native issuance + bridged-in supply.
            # Token Terminal exposes these as two separate metric_ids; requesting
            # both in one call and summing them yields the bridged-inclusive total.
            "metric_id": "ecosystem_stablecoin_supply,ecosystem_bridged_stablecoin_supply",
            "date_field": "timestamp",
            "value_field": [
                "ecosystem_stablecoin_supply",
                "ecosystem_bridged_stablecoin_supply",
            ],
            "methodology": (
                "Total stablecoin supply on Solana = native issuance "
                "(ecosystem_stablecoin_supply) + bridged-in supply "
                "(ecosystem_bridged_stablecoin_supply). Circulating supply excludes "
                "issuer treasury and pre-minted, not-yet-issued balances."
            ),
        },
        "defi_dex_volume": {
            "metric_id": "ecosystem_dex_trading_volume",
            "date_field": "timestamp",
            "value_field": "ecosystem_dex_trading_volume",
            "methodology": "DEX trade volume varies by indexed venues, pricing, and filtering methodology.",
        },
        "network_sol_price": {
            "metric_id": "price",
            "date_field": "timestamp",
            "value_field": "price",
        },
        "network_total_stake": {
            # Staking market cap is native staked SOL priced in USD; dividing by the
            # same published price recovers the staked SOL amount.
            "metric_id": "staking_market_cap,price",
            "date_field": "timestamp",
            "value_field": ["staking_market_cap", "price"],
            "combine": "ratio",
            "methodology": (
                "Total staked SOL, taken as Token Terminal's staking market cap (USD) "
                "divided by the same daily SOL price used to build it. The underlying "
                "figure is the SOL held across native stake accounts, so activating "
                "and deactivating stake are included alongside active stake."
            ),
        },
        "network_validator_count": {
            "metric_id": "number_of_validators",
            "date_field": "timestamp",
            "value_field": "number_of_validators",
            "methodology": (
                "Validators are counted from Solana's native rewards system: an "
                "address counts for a day if it received a voting reward on that "
                "day, which only happens for validators taking part in consensus. "
                "Validators that were delinquent for the whole day therefore drop "
                "out of the count."
            ),
        },
    }

    # Metric key -> (metric model, metric type) used to build the typed record.
    METRIC_TYPE_MAP: Dict[str, Any] = {
        "overview_tx_count_total": (Overview, OverviewMetricType.TX_COUNT_TOTAL),
        "overview_tx_count_vote": (Overview, OverviewMetricType.TX_COUNT_VOTE),
        "overview_sol_price": (Overview, OverviewMetricType.SOL_PRICE),
        "overview_fee_payers": (Overview, OverviewMetricType.FEE_PAYERS),
        "overview_fees": (Overview, OverviewMetricType.FEES),
        "stablecoin_supply": (Stablecoin, StablecoinMetricType.SUPPLY),
        "defi_dex_volume": (Defi, DefiMetricType.DEX_VOLUME),
        "network_sol_price": (Network, NetworkMetricType.SOL_PRICE),
        "network_total_stake": (Network, NetworkMetricType.TOTAL_STAKE),
        "network_validator_count": (Network, NetworkMetricType.VALIDATOR_COUNT),
    }

    BASE_URL = "https://api.tokenterminal.com/v2"
    PROJECT = "solana"

    def __init__(self, *, api_key: Optional[str] = None) -> None:
        resolved_api_key = api_key or self._resolve_api_key()
        if not resolved_api_key:
            raise ValueError("API key is required")
        super().__init__(
            name="TokenTerminal",
            base_url=self.BASE_URL,
            api_key=resolved_api_key,
        )
        self._session = requests.Session()

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        return os.environ.get("TOKEN_TERMINAL_API_KEY")

    @staticmethod
    def _combine(values: List[Any], mode: str) -> Optional[float]:
        """Reduce one day's per-field values into a single figure.

        "sum" adds the values that are present. If one series has no value for a
        date (e.g. bridged stablecoin supply before any bridged stablecoins
        existed on the chain), the absent series is treated as zero and the day
        still reports the available total. Only days with no values at all are
        dropped.

        "ratio" divides the first value by the second, which is how a
        USD-denominated Token Terminal metric is converted back to SOL. Both
        values are required, so a day missing either one is dropped rather than
        reported as a partial figure.
        """
        if mode == "ratio":
            numerator, denominator = values
            if numerator is None or not denominator:
                return None
            return float(numerator) / float(denominator)

        present = [value for value in values if value is not None]
        if not present:
            return None
        return sum(float(value) for value in present)

    def _get(self, endpoint: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        resp = self._session.get(url, headers=headers, params=params or {}, timeout=60)
        resp.raise_for_status()
        return resp.json()

    # -- BaseProvider interface ---------------------------------------------

    @property
    def provider_name(self) -> str:
        return self.name

    def fetch_rows(
        self, metric: str, start_date: str, end_date: str, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Return normalized {"date": str, "value": float} records for the given range (both dates inclusive)."""
        config = self.METRIC_MAP[metric]
        # A metric may map to one or more Token Terminal metric_ids. When several
        # are provided, "combine" decides how that day's values are reduced into a
        # single figure: "sum" (the default) or "ratio". See _combine.
        combine = config.get("combine", "sum")
        value_fields = config["value_field"]
        if isinstance(value_fields, str):
            value_fields = [value_fields]
        body = self._get(
            f"/projects/{self.PROJECT}/metrics",
            params={
                "metric_ids": config["metric_id"],
                "start": start_date,
                "end": end_date,
                "granularity": "day",
            },
        )
        raw = body if isinstance(body, list) else body.get("data", [])
        result = []
        for row in raw:
            row_date = str(row.get(config["date_field"], ""))[:10]
            if not row_date or not (start_date <= row_date <= end_date):
                continue
            value = self._combine([row.get(field) for field in value_fields], combine)
            if value is None:
                continue
            result.append({"date": row_date, "value": value})
        return result

    def get_metric(
        self, metric: str, date: str, chain: str
    ) -> Stablecoin | Overview | Defi | Network | None:
        """Fetch one metric value and return it as a typed metric model."""
        rows = self.fetch_rows(metric, date, date)
        if not rows:
            return None

        metric_model, metric_type = self.METRIC_TYPE_MAP[metric]
        return metric_model.from_metric_type(
            metric_type=metric_type,
            date=datetime.date.fromisoformat(date),
            value=rows[0]["value"],
        )
