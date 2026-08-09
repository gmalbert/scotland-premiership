"""League-owned configuration for a thin Pitch Oracle consumer."""

from dataclasses import replace

from pitch_oracle_core import get_league_config


# Open-Meteo needs one coordinate per home ground.  Keep these in the consumer
# so Scottish forecast coverage does not depend on EPL-specific core data.
STADIUM_COORDINATES = {
    "Aberdeen": (57.1592, -2.0889),
    "Celtic": (55.8497, -4.2055),
    "Dundee": (56.4747, -2.9733),
    "Dundee United": (56.4746, -2.9680),
    "Falkirk": (55.9992, -3.7525),
    "Heart of Midlothian": (55.9390, -3.2325),
    "Hibernian": (55.9617, -3.1653),
    "Kilmarnock": (55.6042, -4.5081),
    "Livingston": (55.8860, -3.5210),
    "Motherwell": (55.7800, -3.9803),
    "Rangers": (55.8532, -4.3093),
    "Ross County": (57.5955, -4.4184),
    "St Johnstone": (56.4096, -3.4765),
    "St Mirren": (55.8931, -4.3923),
}


# Replace with any key in pitch_oracle_core.BUILTIN_LEAGUES.
LEAGUE_CONFIG = replace(
    get_league_config("scotland"),
    stadium_coordinates=STADIUM_COORDINATES,
)
