import pandas as pd

from scripts.fetch_odds import _best_moneyline, _find_league_slug, _match_fixture
from scripts.precompute_predictions import (
    add_market_recommendations,
    clear_unavailable_weather_defaults,
)


def test_find_scottish_premiership_slug():
    leagues = [{"name": "Scotland - Premiership", "slug": "scotland-premiership"}]
    assert _find_league_slug(leagues) == "scotland-premiership"


def test_fixture_match_handles_hearts_alias():
    fixtures = pd.DataFrame(
        [{"Date": "2026-08-09", "HomeTeam": "Heart of Midlothian", "AwayTeam": "Dundee United"}]
    ).assign(
        _date=pd.to_datetime(["2026-08-09T10:00:00Z"], utc=True),
        _home=["hearts"],
        _away=["dundee united"],
    )
    event = {"home": "Hearts FC", "away": "Dundee United FC", "date": "2026-08-09T14:00:00Z"}
    assert _match_fixture(event, fixtures)["HomeTeam"] == "Heart of Midlothian"


def test_best_moneyline_uses_best_price_for_each_outcome():
    event = {
        "bookmakers": {
            "Bet365": [{"name": "ML", "odds": [{"home": "2.10", "draw": "3.20", "away": "3.40"}]}],
            "Unibet": [{"name": "ML", "odds": [{"home": "2.20", "draw": "3.10", "away": "3.50"}]}],
        }
    }
    result = _best_moneyline(event)
    assert result["OddsHome"] == 2.2
    assert result["OddsDraw"] == 3.2
    assert result["OddsAway"] == 3.5
    assert result["OddsHomeBookmaker"] == "Unibet"


def test_market_recommendation_replaces_unavailable_fallback(tmp_path):
    predictions = pd.DataFrame(
        [{
            "Date": "2026-08-09", "HomeTeam": "Rangers", "AwayTeam": "Hibernian",
            "HomeWin_Prob": 0.60, "Draw_Prob": 0.22, "AwayWin_Prob": 0.18,
            "BetRecommendation": "No bet",
            "BetReason": "Market odds unavailable; betting value cannot be established.",
        }]
    )
    odds_path = tmp_path / "odds.csv"
    pd.DataFrame(
        [{
            "Date": "2026-08-09", "HomeTeam": "Rangers", "AwayTeam": "Hibernian",
            "OddsHome": 2.0, "OddsDraw": 3.5, "OddsAway": 4.0,
            "OddsHomeBookmaker": "Bet365", "OddsDrawBookmaker": "Bet365",
            "OddsAwayBookmaker": "Unibet",
        }]
    ).to_csv(odds_path, index=False)

    result = add_market_recommendations(predictions, odds_path)
    assert result.loc[0, "BetRecommendation"] == "Bet Home Win"
    assert "Bet365" in result.loc[0, "BetReason"]


def test_unavailable_weather_does_not_claim_zero_rain():
    frame = pd.DataFrame(
        [{
            "Temperature": None,
            "Humidity": None,
            "WindSpeed": None,
            "Precipitation": 0,
            "WeatherDescription": "Unknown",
        }]
    )

    result = clear_unavailable_weather_defaults(frame)

    assert pd.isna(result.loc[0, "Precipitation"])
