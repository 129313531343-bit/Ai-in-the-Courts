/**
 * Law report series the parser recognises (AGLC4 abbreviations).
 *
 * Recognising a series only means the parser reads the citation. Whether it can be checked
 * depends on the report index, which records the series actually cited in the corpus.
 * "round": (year) volume SERIES page. "square": [year] (volume) SERIES page.
 */
export interface Series {
  abbr: string;
  name: string;
  style: "round" | "square";
}

export const SERIES: readonly Series[] = [
  { abbr: "CLR", name: "Commonwealth Law Reports", style: "round" },
  { abbr: "ALR", name: "Australian Law Reports", style: "round" },
  { abbr: "ALJR", name: "Australian Law Journal Reports", style: "round" },
  { abbr: "FCR", name: "Federal Court Reports", style: "round" },
  { abbr: "FLR", name: "Federal Law Reports", style: "round" },
  { abbr: "NSWLR", name: "New South Wales Law Reports", style: "round" },
  { abbr: "SR (NSW)", name: "State Reports (New South Wales)", style: "round" },
  { abbr: "VR", name: "Victorian Reports", style: "square" },
  { abbr: "VLR", name: "Victorian Law Reports", style: "round" },
  { abbr: "Qd R", name: "Queensland Reports", style: "square" },
  { abbr: "SASR", name: "South Australian State Reports", style: "round" },
  { abbr: "WAR", name: "Western Australian Reports", style: "round" },
  { abbr: "Tas R", name: "Tasmanian Reports", style: "round" },
  { abbr: "ACTR", name: "Australian Capital Territory Reports", style: "round" },
  { abbr: "NTR", name: "Northern Territory Reports", style: "round" },
  { abbr: "NTLR", name: "Northern Territory Law Reports", style: "round" },
  { abbr: "Fam LR", name: "Family Law Reports", style: "round" },
  { abbr: "A Crim R", name: "Australian Criminal Reports", style: "round" },
  { abbr: "ACSR", name: "Australian Corporations and Securities Reports", style: "round" },
  { abbr: "ACLC", name: "Australian Company Law Cases", style: "round" },
  { abbr: "IPR", name: "Intellectual Property Reports", style: "round" },
  { abbr: "ALD", name: "Administrative Law Decisions", style: "round" },
  { abbr: "IR", name: "Industrial Reports", style: "round" },
  { abbr: "LGERA", name: "Local Government and Environmental Reports of Australia", style: "round" },
  { abbr: "MVR", name: "Motor Vehicle Reports", style: "round" },
  { abbr: "ATR", name: "Australian Tax Reports", style: "round" },
  { abbr: "ATC", name: "Australian Tax Cases", style: "round" },
  { abbr: "AC", name: "Law Reports, Appeal Cases (UK)", style: "square" },
  { abbr: "QB", name: "Law Reports, Queen's Bench (UK)", style: "square" },
  { abbr: "KB", name: "Law Reports, King's Bench (UK)", style: "square" },
  { abbr: "Ch", name: "Law Reports, Chancery (UK)", style: "square" },
  { abbr: "WLR", name: "Weekly Law Reports (UK)", style: "square" },
  { abbr: "All ER", name: "All England Law Reports", style: "square" },
  { abbr: "NZLR", name: "New Zealand Law Reports", style: "square" },
];

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
