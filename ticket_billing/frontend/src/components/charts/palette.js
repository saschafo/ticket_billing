// Gedeckte, klar unterscheidbare Farben für Diagrammserien.
//
// Bewusst keine Signalfarben: Die Diagramme stehen neben Tabellen und
// Kennzahlen, und ein greller Verlauf zöge den Blick von den Zahlen weg.
// Die Reihenfolge ist fest — dieselbe Abteilung oder derselbe Mitarbeiter
// behält beim Wechsel des Zeitraums seine Farbe, sonst müsste man die
// Legende jedes Mal neu lesen.
export const SERIES_COLORS = [
  '#3d6fb3', // Blau
  '#d98a3d', // Orange
  '#4f9d69', // Grün
  '#b8973a', // Gelb-Ocker
  '#7a6fa8', // Violett
  '#a8574f', // Rotbraun
  '#4a8f96', // Petrol
]

export const seriesColor = (index) => SERIES_COLORS[index % SERIES_COLORS.length]

// Farben für die feste Zweiteilung intern/extern. Extern ist die
// abrechenbare Seite und bekommt deshalb die kräftigere Farbe.
export const ORIGIN_COLORS = {
  External: '#3d6fb3',
  Internal: '#b9c2cc',
}

/** Achsen, Raster und Schrift -- an allen Diagrammen gleich. */
export const GRID_COLOR = '#e8ecf1'
export const TICK_COLOR = '#94a3b8'
export const FONT_FAMILY =
  'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
