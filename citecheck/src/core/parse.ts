/**
 * Deterministic citation parser (AGLC4 forms). No network, no model: the same text always
 * gives the same citations, and the evaluation harness runs exactly this code.
 *
 * Reads:
 *   - medium neutral citations: Smith v Jones [2019] NSWSC 123 at [45]
 *   - law report citations:     Mabo v Queensland (No 2) (1992) 175 CLR 1, 15
 *                               Smith v Jones [1990] 1 Qd R 5; Donoghue v Stevenson [1932] AC 562
 *   - Acts and sections:        Competition and Consumer Act 2010 (Cth) sch 2 s 18;
 *                               s 18 of the Australian Consumer Law; Corporations Act s 1041H
 */
import courtsData from "./data/courts.json" with { type: "json" };
import { SERIES_PATTERN, findSeries } from "./series.ts";
import type { CaseCitation, Citation, Provision, StatuteCitation } from "./types.ts";

export interface Court {
  code: string;
  name: string;
  jurisdiction: string;
  level: string;
}

export const COURTS: ReadonlyMap<string, Court> = new Map((courtsData as Court[]).map((c) => [c.code, c]));

/**
 * One-for-one character clean-up (curly quotes, dashes, odd spaces, line breaks), so every
 * offset in the cleaned text is also an offset in the original.
 */
export function normaliseChars(text: string): string {
  return text
    .replace(/[\u2018\u2019\u201A\u201B\u2032]/g, "'")
    .replace(/[\u201C\u201D\u201E]/g, '"')
    .replace(/[\u2010-\u2015\u2212]/g, "-")
    .replace(/[\u00A0\u2002-\u200A\u202F\r\n\t]/g, " ");
}

const YEAR = String.raw`(?:1[6-9]\d\d|20\d\d)`;
const MNC_RE = new RegExp(String.raw`\[\s*(${YEAR})\s*\]\s+([A-Z][A-Za-z0-9]{1,11})\s+(\d{1,5})(?![\d])`, "g");
const REPORT_RE = new RegExp(
  String.raw`([(\[])\s*(${YEAR})(?:\s*-\s*(?:\d{2}|\d{4}))?\s*[)\]]\s+(?:(\d{1,4})\s+)?(${SERIES_PATTERN})\s+(\d{1,5})(?![\d])`,
  "g",
);
const PARA = String.raw`\[\d+\](?!\s*[A-Z][A-Za-z0-9]{1,11}\s+\d)`; // "[2020] NSWCA 2" is a citation, not a paragraph
const MNC_PINPOINT = new RegExp(String.raw`^(\s*,?\s*(?:at\s+)?)(${PARA}(?:\s*-\s*${PARA})?(?:\s*(?:,|and)\s*${PARA}(?:\s*-\s*${PARA})?)*)`);
const REPORT_PINPOINT = /^(\s*(?:,|at)\s*)(\d+(?:\s*-\s*\d+)?(?:\s*,\s*\d+(?:\s*-\s*\d+)?)*(?:\s*\[\d+\])?)(?![\d\]])/;

// Words that can sit inside a party name without a capital letter.
const CONNECTORS = new Set(["v", "and", "of", "for", "the", "de", "du", "da", "van", "von", "der", "den", "la", "le",
  "parte", "&", "as", "trading", "t/as", "on", "behalf", "by"]);
// Capitalised words that start a sentence or clause rather than a party name.
const LEAD_WORDS = new Set(["See", "In", "Cf", "Compare", "Also", "As", "Following", "Applying", "Per", "Accordingly",
  "Thus", "However", "And", "But", "Under", "Unlike", "Like", "Contrast", "Further", "Similarly", "Approved",
  "Affirmed", "Applied", "Considered", "Distinguished", "Followed", "Citing", "Discussing", "From", "Since",
  "Although", "While", "Whereas", "Because", "Where", "When", "That", "This", "These", "Then", "Therefore",
  "Moreover", "Indeed", "Nonetheless", "Notably", "Relevantly", "Here", "There", "It", "He", "She", "They", "We"]);
const PARTY_TOKEN = /\((?:[^()]{1,40})\)|[A-Za-z0-9][\w'./&-]*|;|&/g;

/** Party names written just before position end, or null. */
export function partiesBefore(text: string, end: number, floor = 0): { parties: string; start: number } | null {
  const windowStart = Math.max(floor, end - 220);
  const before = text.slice(windowStart, end);
  const tokens = [...before.matchAll(PARTY_TOKEN)].map((m) => ({ t: m[0], i: windowStart + m.index }));
  // The party name must run right up to the citation (only spaces between).
  if (!tokens.length) return null;
  const lastTok = tokens[tokens.length - 1]!;
  if (text.slice(lastTok.i + lastTok.t.length, end).trim() !== "") return null;
  let k = tokens.length;
  while (k > 0) {
    const tok = tokens[k - 1]!;
    const next = tokens[k];
    const gap = next ? text.slice(tok.i + tok.t.length, next.i) : "";
    if (/[.,:!?"]/.test(gap)) break; // punctuation between words ends the name
    const t = tok.t;
    if (t === ";") {
      if (next && /^(Ex|Re)$/.test(next.t)) { k--; continue; }
      break;
    }
    if (/\.$/.test(t) && !/^(?:No|Co|Pty|Ltd|Inc|St|Mt|Dr|Bros|Corp|Assn|v|[A-Z])\.$/.test(t)) break; // sentence end
    if (/^\(/.test(t) || /^[A-Z]/.test(t) || CONNECTORS.has(t) || t === "v." || t === "ex") { k--; continue; }
    break;
  }
  let picked = tokens.slice(k);
  // Drop lead-in words and stray connectors at the front ("See", "In", "and", "the").
  while (picked.length) {
    const first = picked[0]!.t;
    const second = picked[1]?.t ?? "";
    if (first === "In" && /^(re|the|Re|The)$/.test(second)) break; // "In re X", "In the Marriage of X"
    if (LEAD_WORDS.has(first) || (CONNECTORS.has(first) && first !== "&") || first === ";" || /^\(/.test(first)) {
      picked = picked.slice(1);
      continue;
    }
    break;
  }
  if (!picked.length) return null;
  const start = picked[0]!.i;
  const parties = text.slice(start, end).trim().replace(/\s+/g, " ");
  const named = / v\.? /.test(` ${parties} `) || /^(Re|In re|In the [Mm]atter of|In the Marriage of|Ex parte|R \(|Application by|Application of)\b/.test(parties);
  return named ? { parties, start } : null;
}

/** Case citations without their party names; parties are attached later by attachParties. */
function caseCores(clean: string): CaseCitation[] {
  const found: CaseCitation[] = [];
  for (const m of clean.matchAll(REPORT_RE)) {
    const [whole, bracket, year, vol, seriesWritten, page] = m;
    const series = findSeries(seriesWritten!);
    if (!series) continue;
    const citeStart = m.index;
    let citeEnd = citeStart + whole.length;
    const pin = REPORT_PINPOINT.exec(clean.slice(citeEnd));
    if (pin) citeEnd += pin[0].length;
    found.push({
      kind: "report", raw: "", start: citeStart, end: citeEnd, parties: null, year: Number(year),
      series: series.abbr, volume: vol ? Number(vol) : null, page: Number(page),
      bracket: bracket === "(" ? "round" : "square", pinpoint: pin ? pin[2]!.trim() : null,
    });
  }
  for (const m of clean.matchAll(MNC_RE)) {
    const [whole, year, court, num] = m;
    if (findSeries(court!)) continue; // "[1990] VR 1" is a report, read above
    const citeStart = m.index;
    if (found.some((f) => citeStart >= f.start && citeStart < f.end)) continue;
    let citeEnd = citeStart + whole.length;
    const pin = MNC_PINPOINT.exec(clean.slice(citeEnd));
    if (pin) citeEnd += pin[0].length;
    found.push({
      kind: "mnc", raw: "", start: citeStart, end: citeEnd, parties: null, year: Number(year), court,
      number: Number(num), pinpoint: pin ? pin[2]!.trim() : null,
    });
  }
  return found.sort((a, b) => a.start - b.start);
}

/** Party names for each case citation, never reaching back past the previous citation or a statute. */
function attachParties(found: CaseCitation[], statutes: StatuteCitation[], clean: string, original: string): void {
  let prev: CaseCitation | null = null;
  for (const c of found) {
    const floor = Math.max(prev?.end ?? 0, ...statutes.filter((s) => s.end <= c.start).map((s) => s.end));
    const p = partiesBefore(clean, c.start, floor);
    if (p) {
      c.parties = original.slice(p.start, c.start).trim().replace(/\s+/g, " ");
      c.start = p.start;
    } else if (prev?.parties && /^\s*[;,]\s*$/.test(clean.slice(prev.end, c.start))) {
      c.parties = prev.parties; // parallel citation: "(2008) 236 CLR 573; [2008] HCA 36"
    }
    c.raw = original.slice(c.start, c.end);
    prev = c;
  }
}

const JURIS = String.raw`Cth|NSW|Vic|Qld|WA|SA|Tas|ACT|NT|Imp|UK|NZ`;
const CAPWORD = String.raw`[A-Z][A-Za-z'-]*`;
const TITLE_PAREN = String.raw`\((?:[A-Z][A-Za-z' -]*|No\.? \d+)\)`;
const CONNECT = String.raw`and|of|the|for|to|on|in|with|by|at|or|de`;
const TITLE = String.raw`(?:${CAPWORD}|${TITLE_PAREN})(?:\s+(?:${CAPWORD}|${CONNECT}|${TITLE_PAREN}))*?\s+Act`;
const ACT_RE = new RegExp(String.raw`\b(${TITLE})(?:\s+(${YEAR}))?(?:\s*\((${JURIS})\))?`, "g");
const ACL_RE = new RegExp(String.raw`\b(Australian Consumer Law|ACL)\b(?:\s*\((${JURIS})\))?`, "g");
const SEC = String.raw`\d+[A-Z]{0,3}(?:\(\w{1,4}\))*`;
const SEC_LIST = String.raw`${SEC}(?:\s*(?:-|and|,|to|or)\s*${SEC})*`;
const AFTER_RE = new RegExp(
  String.raw`^\s*,?\s*(?:(?:sch|schedule)\s+(\d+[A-Z]?)\s*,?\s*)?(?:(?:pt|part|div|division)\s+[\dA-Z.]+\s*,?\s*)*(?:ss?|sections?)\.?\s+(${SEC_LIST})`,
  "i",
);
const BEFORE_RE = new RegExp(
  String.raw`\b(?:ss?|sections?)\.?\s+(${SEC_LIST})\s+(?:of\s+)?(?:(?:sch|schedule)\s+(\d+[A-Z]?)\s+(?:to|of)\s+)?(?:the\s+)?$`,
  "i",
);
const TITLE_LEAD = new Set([...LEAD_WORDS, "The", "Section", "Sections", "Pursuant", "By", "Of", "Both", "Either", "Neither",
  "Despite", "Contrary", "If", "Part", "Pt", "Division", "Div", "Schedule", "Sch", "Those"]);

function provisionsFrom(list: string, schedule: string | undefined): Provision[] {
  return list
    .split(/\s*(?:-|and|,|to|or)\s*/)
    .filter(Boolean)
    .map((section) => (schedule ? { schedule, section } : { section }));
}

function statuteCitations(clean: string, original: string, taken: (s: number, e: number) => boolean): StatuteCitation[] {
  const out: StatuteCitation[] = [];
  const add = (start: number, titleEnd: number, cite: Omit<StatuteCitation, "raw" | "start" | "end" | "provisions">,
    defaultSchedule?: string, needProvisions = false) => {
    let s = start;
    let e = titleEnd;
    const provisions: Provision[] = [];
    const before = BEFORE_RE.exec(clean.slice(Math.max(0, s - 90), s));
    if (before) {
      provisions.push(...provisionsFrom(before[1]!, before[2] ?? defaultSchedule));
      s -= before[0].length;
    }
    const after = AFTER_RE.exec(clean.slice(e));
    if (after) {
      provisions.push(...provisionsFrom(after[2]!, after[1] ?? defaultSchedule));
      e += after[0].length;
    }
    if (!provisions.length && (needProvisions || (cite.year === null && !cite.alias))) return; // too vague alone
    if (taken(s, e)) return;
    out.push({ ...cite, raw: original.slice(s, e).trim(), start: s, end: e, provisions });
  };
  for (const m of clean.matchAll(ACT_RE)) {
    let title = m[1]!;
    let start = m.index;
    // Trim lead-in words the greedy title picked up ("Under the Migration Act" -> "Migration Act").
    for (;;) {
      const w = /^(\S+)\s+/.exec(title);
      if (!w) break;
      const word = w[1]!;
      if (TITLE_LEAD.has(word) || /^[a-z]/.test(word)) {
        title = title.slice(w[0].length);
        start += w[0].length;
        continue;
      }
      break;
    }
    if (title.split(/\s+/).length < 2) continue; // "Act" alone
    add(start, m.index + m[0].length, {
      kind: "statute", title, year: m[2] ? Number(m[2]) : null, jurisdiction: m[3] ?? null, alias: null,
    });
  }
  for (const m of clean.matchAll(ACL_RE)) {
    add(m.index, m.index + m[0].length, {
      kind: "statute", title: "Competition and Consumer Act", year: 2010, jurisdiction: m[2] ?? "Cth",
      alias: "Australian Consumer Law",
    }, "2", m[1] === "ACL");
  }
  return out;
}

/** Every case and statute citation in text, in order. */
export function parseCitations(text: string): Citation[] {
  const clean = normaliseChars(text);
  const cases = caseCores(clean);
  const overlaps = (s: number, e: number) => cases.some((c) => s < c.end && e > c.start);
  const statutes = statuteCitations(clean, text, overlaps);
  attachParties(cases, statutes, clean, text);
  return [...cases, ...statutes].sort((a, b) => a.start - b.start);
}
