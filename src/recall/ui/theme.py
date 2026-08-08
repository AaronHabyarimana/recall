"""Farben und Diagramm-Bausteine der Oberfläche.

Alle Diagramme zeigen eine einzelne Messreihe (wie viele Karten wann, wie oft welche
Bewertung), also durchgängig eine Blau-Rampe statt bunter Kategorienfarben - die
Farbe kodiert Menge, nicht Identität. Die Rampenstufen sind gegen die helle Fläche
`#fcfcfb` auf Monotonie, Stufenabstand und Kontrast geprüft.
"""

import altair as alt
import pandas as pd

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES = "#2a78d6"
# geordnete Rampe hell -> dunkel für die vier Bewertungsstufen
ORDINAL = ["#86b6ef", "#5598e7", "#2a78d6", "#184f95"]

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _konfiguriert(chart: alt.Chart, hoehe: int) -> alt.Chart:
    """Gemeinsames Erscheinungsbild: zurückhaltende Achsen, kein Rahmen, kein Titelchrom."""
    return (
        chart.properties(height=hoehe, background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            domainColor=AXIS,
            tickColor=AXIS,
            gridColor=GRID,
            labelFont=FONT,
            titleFont=FONT,
            labelFontSize=12,
            titleFontSize=12,
        )
        .configure_text(font=FONT)
    )


def verlaufsdiagramm(daten: list[tuple[str, int]]) -> alt.Chart:
    """Senkrechte Balken über die Tage - wie viele Karten wann fällig werden."""
    df = pd.DataFrame(daten, columns=["tag", "anzahl"])
    df["datum"] = pd.to_datetime(df["tag"])
    df["label"] = [
        f"{WOCHENTAGE[d.weekday()]} {d.day:02d}.{d.month:02d}." for d in df["datum"]
    ]
    df.loc[0, "label"] = "heute"

    balken = (
        alt.Chart(df)
        .mark_bar(
            color=SERIES,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
        )
        .encode(
            x=alt.X(
                "label:N",
                sort=None,
                title=None,
                axis=alt.Axis(labelAngle=0, labelPadding=6),
                scale=alt.Scale(paddingInner=0.3),
            ),
            y=alt.Y("anzahl:Q", title="Karten", axis=alt.Axis(tickMinStep=1, grid=True)),
            tooltip=[
                alt.Tooltip("label:N", title="Tag"),
                alt.Tooltip("anzahl:Q", title="fällige Karten"),
            ],
        )
    )
    return _konfiguriert(balken, hoehe=220)


def rangdiagramm(
    beschriftungen: list[str], werte: list[int], *, farben: list[str] | None = None
) -> alt.Chart:
    """Waagerechte Balken mit direkter Beschriftung.

    Waagerecht, weil die Kategorien ausgeschriebene Wörter sind ("kontextabhaengig")
    und senkrecht gedrehte Achsenbeschriftungen niemand lesen will.
    """
    df = pd.DataFrame({"kategorie": beschriftungen, "anzahl": werte})
    palette = farben or [SERIES] * len(beschriftungen)

    grund = alt.Chart(df).encode(
        y=alt.Y("kategorie:N", sort=None, title=None, axis=alt.Axis(labelPadding=8)),
        x=alt.X("anzahl:Q", title=None, axis=None),
    )
    balken = grund.mark_bar(
        cornerRadiusTopRight=4,
        cornerRadiusBottomRight=4,
        height=alt.RelativeBandSize(0.62),
    ).encode(
        color=alt.Color(
            "kategorie:N",
            sort=None,
            scale=alt.Scale(domain=beschriftungen, range=palette),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("kategorie:N", title=""),
            alt.Tooltip("anzahl:Q", title="Karten"),
        ],
    )
    # Direkte Beschriftung statt Werteachse: bei wenigen Balken ist die Zahl am Balken
    # schneller zu lesen als der Umweg über eine Achse.
    beschriftung = grund.mark_text(
        align="left", dx=6, color=MUTED, fontSize=12, font=FONT
    ).encode(text="anzahl:Q")

    return _konfiguriert(balken + beschriftung, hoehe=max(90, 42 * len(beschriftungen)))
