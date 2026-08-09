"""Fetch Scottish Premiership 1X2 odds from Odds-API.io."""

from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd
import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.odds-api.io/v3"
DEFAULT_BOOKMAKERS = "Bet365,Unibet"
TEAM_ALIASES = {
    "heart of midlothian": "hearts",
    "heart of midlothian fc": "hearts",
}


def _normalise_team(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"\b(?:football club|fc|afc)\b", "", text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return TEAM_ALIASES.get(text, text)


def _get_json(path: str, api_key: str, **params: object) -> object:
    response = requests.get(
        f"{API_ROOT}/{path}",
        params={"apiKey": api_key, **params},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"Odds-API.io {path} request failed ({response.status_code}): {detail}") from exc
    return response.json()


def _find_league_slug(leagues: object) -> str:
    if not isinstance(leagues, list):
        raise RuntimeError("Odds-API.io returned an unexpected leagues response.")
    candidates = []
    for league in leagues:
        if not isinstance(league, dict):
            continue
        name = str(league.get("name", "")).lower()
        slug = str(league.get("slug", ""))
        if "scotland" in name and "premiership" in name:
            return slug
        if ("scotland" in name or "scottish" in name) and "premier" in name:
            candidates.append(slug)
    if candidates:
        return candidates[0]
    raise RuntimeError("Scottish Premiership was not found in the Odds-API.io league list.")


def _match_fixture(event: dict[str, object], fixtures: pd.DataFrame) -> pd.Series | None:
    home = _normalise_team(event.get("home"))
    away = _normalise_team(event.get("away"))
    event_date = pd.to_datetime(event.get("date"), utc=True, errors="coerce")
    matches = fixtures[
        (fixtures["_home"] == home)
        & (fixtures["_away"] == away)
        & ((fixtures["_date"] - event_date).abs() <= pd.Timedelta(days=1))
    ]
    return None if matches.empty else matches.iloc[0]


def _best_moneyline(event: dict[str, object]) -> dict[str, object] | None:
    best = {
        "home": (0.0, ""),
        "draw": (0.0, ""),
        "away": (0.0, ""),
    }
    bookmakers = event.get("bookmakers", {})
    if not isinstance(bookmakers, dict):
        return None
    for bookmaker, markets in bookmakers.items():
        if not isinstance(markets, list):
            continue
        market = next(
            (item for item in markets if isinstance(item, dict) and str(item.get("name", "")).upper() == "ML"),
            None,
        )
        prices = market.get("odds", []) if market else []
        if not prices or not isinstance(prices[0], dict):
            continue
        for outcome in best:
            try:
                price = float(prices[0].get(outcome, 0))
            except (TypeError, ValueError):
                continue
            if price > best[outcome][0]:
                best[outcome] = (price, str(bookmaker))
    if any(price <= 1.0 for price, _ in best.values()):
        return None
    return {
        "OddsHome": best["home"][0],
        "OddsDraw": best["draw"][0],
        "OddsAway": best["away"][0],
        "OddsHomeBookmaker": best["home"][1],
        "OddsDrawBookmaker": best["draw"][1],
        "OddsAwayBookmaker": best["away"][1],
    }


def fetch() -> Path | None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        print("ODDS_API_KEY is not configured; leaving betting odds unavailable.")
        return None

    bookmakers = os.getenv("ODDS_API_BOOKMAKERS", DEFAULT_BOOKMAKERS).strip()
    if not bookmakers:
        raise RuntimeError("ODDS_API_BOOKMAKERS must contain at least one bookmaker.")

    fixtures_path = ROOT / "data_files" / "upcoming_fixtures.csv"
    fixtures = pd.read_csv(fixtures_path)
    fixture_time_values = fixtures["Time"].astype(str) if "Time" in fixtures else pd.Series("00:00", index=fixtures.index)
    fixture_times = pd.to_datetime(
        fixtures["Date"].astype(str) + " " + fixture_time_values,
        utc=True,
        errors="coerce",
    )
    fixtures = fixtures.assign(
        _date=fixture_times,
        _home=fixtures["HomeTeam"].map(_normalise_team),
        _away=fixtures["AwayTeam"].map(_normalise_team),
    )
    if fixture_times.isna().all():
        raise RuntimeError("Upcoming fixtures contain no valid dates.")

    leagues = _get_json("leagues", api_key, sport="football", all="true")
    league_slug = _find_league_slug(leagues)
    start = fixture_times.min().floor("D") - timedelta(days=1)
    end = fixture_times.max().ceil("D") + timedelta(days=1)
    events = _get_json(
        "events",
        api_key,
        sport="football",
        league=league_slug,
        status="pending",
        **{"from": start.isoformat().replace("+00:00", "Z"), "to": end.isoformat().replace("+00:00", "Z")},
    )
    if not isinstance(events, list):
        raise RuntimeError("Odds-API.io returned an unexpected events response.")

    matched = []
    for event in events:
        if isinstance(event, dict):
            fixture = _match_fixture(event, fixtures)
            if fixture is not None:
                matched.append((event, fixture))

    odds_by_id: dict[str, dict[str, object]] = {}
    event_ids = [str(event["id"]) for event, _ in matched]
    for offset in range(0, len(event_ids), 10):
        batch = _get_json(
            "odds/multi",
            api_key,
            eventIds=",".join(event_ids[offset : offset + 10]),
            bookmakers=bookmakers,
        )
        if not isinstance(batch, list):
            raise RuntimeError("Odds-API.io returned an unexpected multi-odds response.")
        odds_by_id.update({str(item["id"]): item for item in batch if isinstance(item, dict) and "id" in item})

    rows = []
    for event, fixture in matched:
        prices = _best_moneyline(odds_by_id.get(str(event["id"]), {}))
        if prices:
            rows.append(
                {
                    "Date": fixture["Date"],
                    "HomeTeam": fixture["HomeTeam"],
                    "AwayTeam": fixture["AwayTeam"],
                    "OddsProviderEventId": event["id"],
                    **prices,
                }
            )

    output = ROOT / "data_files" / "odds.csv"
    columns = [
        "Date", "HomeTeam", "AwayTeam", "OddsProviderEventId",
        "OddsHome", "OddsDraw", "OddsAway",
        "OddsHomeBookmaker", "OddsDrawBookmaker", "OddsAwayBookmaker",
    ]
    pd.DataFrame(rows, columns=columns).to_csv(output, index=False)
    print(f"Wrote {len(rows)} matched 1X2 markets to {output} using {bookmakers}.")
    return output


if __name__ == "__main__":
    try:
        fetch()
    except Exception as exc:
        print(f"Odds fetch failed: {exc}", file=sys.stderr)
        raise
