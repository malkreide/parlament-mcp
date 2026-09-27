"""openparldata-mcp – MCP-Server für Schweizer Kantons- und Gemeindeparlamente.

Subnationale Ebene (26 Kantone + ~70 Gemeindeparlamente) über die
OpenParlData.ch-API. Die Bundesebene wird bewusst nicht abgedeckt (siehe
``parlament-mcp``).
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

try:
    # Aus den Paket-Metadaten, die aus `pyproject.toml` gebaut werden — wie im
    # Bundes-Server. Hier stand ein zweites Literal `"0.1.0"`, das niemand
    # hielt; seit der Server die Version in jedes `serverInfo` stempelt, waere
    # ein Auseinanderlaufen auf der Leitung sichtbar geworden.
    __version__ = _distribution_version("openparldata-mcp")
except PackageNotFoundError:
    # Quellbaum ohne Installation. Bewusst keine plausible Zahl: eine erkennbar
    # unveroeffentlichte Markierung ist besser als eine falsche Version.
    __version__ = "0.0.0+source"
