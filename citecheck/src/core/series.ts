/**
 * Law report series the parser recognises (AGLC4 abbreviations).
 *
 * Recognising a series only means the parser reads the citation. Whether it can be checked
 * depends on the report index, which records the series actually cited in the corpus.
 * "round": (year) volume SERIES page. "square": [year] (volume) SERIES page; in square series the
 * volumes run within a year, so the year is part of a report's identity (reportKey).
 * The table lives in data/series.json, which the Python build reads too.
 */
import seriesData from "./data/series.json" with { type: "json" };

export interface Series {
  abbr: string;
  name: string;
  style: "round" | "square";
}

export const SERIES: readonly Series[] = seriesData as Series[];

const BY_KEY = new Map(SERIES.map((s) => [seriesKey(s.abbr), s]));

/** Spacing- and case-insensitive key, so "QdR", "Qd R" and "QD R" meet. */
export function seriesKey(abbr: string): string {
  return abbr.replace(/[\s.]/g, "").toUpperCase();
}

export function findSeries(written: string): Series | undefined {
  return BY_KEY.get(seriesKey(written));
}

/** Regex source matching any series, longest first, with flexible spacing and optional full stops. */
export const SERIES_PATTERN = [...SERIES]
  .sort((a, b) => b.abbr.length - a.abbr.length)
  .map((s) =>
    s.abbr
      .split("")
      .map((ch) => (ch === " " ? "\\s*" : /[A-Za-z]/.test(ch) ? `${ch}\\.?` : ch.replace(/[()]/g, "\\$&")))
      .join(""),
  )
  .join("|");

/**
 * Key of a report within its series, as used by index (b): "volume|page", or for square series
 * "year/volume|page" ("[1990] 1 Qd R 5" -> "1990/1|5"; "[1932] AC 562" -> "1932/|562").
 */
export function reportKey(series: string, year: number, volume: number | null | undefined, page: number): string {
  const vol = volume ?? "";
  return findSeries(series)?.style === "square" ? `${year}/${vol}|${page}` : `${vol}|${page}`;
}
