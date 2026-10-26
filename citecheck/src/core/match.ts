/**
 * Check parsed citations against the indexes. One of four states per citation, always with
 * the reason, the record matched (if any) and links for a person to follow:
 *
 *   FOUND         a record with this citation exists (and the party names match, where given)
 *   MISMATCH      a record exists, but its parties (or the Act's year) do not match the citation
 *   NO_RECORD     within what the corpus covers, there is no such record
 *   CANNOT_CHECK  outside coverage: court, date, series, jurisdiction or range not covered
 *
 * FOUND is never "verified" or "good law": it means a record with this citation and these
 * party names exists. Reading the source is still the user's job.
 *
 * DEFAULTS were fixed before the evaluation set was frozen and before any run against it.
 * They may be tuned on the dev split only, after the freeze (DECISIONS.md D029, D037).
 */
import { decodeSides, fingerprintSides, fp } from "./fingerprint.ts";
import { baseSection, fetchSections, type SectionList } from "./legislation.ts";
import { COURTS } from "./parse.ts";
import { findSeries, reportKey, seriesKey } from "./series.ts";
import type { CaseCitation, Citation, StatuteCitation } from "./types.ts";

export type State = "FOUND" | "MISMATCH" | "NO_RECORD" | "CANNOT_CHECK";

export interface Link { label: string; url: string }

export interface Result {
  citation: Citation;
  state: State;
  reason: string;
  /** What was matched: date and official URL for decisions, citing count for reports, title for Acts. */
  record: { date?: string; url?: string; citedBy?: number; usualYear?: number; title?: string } | null;
  links: Link[];
  notes: string[];
}

/** Reads index files: the browser fetches them from the site, Node reads them from disk. */
export interface Loader {
  json<T>(path: string): Promise<T | null>;
  gzJson<T>(path: string): Promise<T | null>;
}

export interface Settings {
  /** No request leaves the site: Commonwealth sections are not checked. */
  offline: boolean;
  /** A court-year with more missing numbers than this cannot show that a decision is absent. */
  gapThreshold: number;
  /** "every_side": each side of the case name must share a word with the record; "any_side": one is enough. */
  partyRule: "every_side" | "any_side";
  /** Date for "the version in force" of a Commonwealth Act (YYYY-MM-DD). */
  asAt: string;
  fetchFn?: typeof fetch;
}

export const DEFAULTS: Omit<Settings, "asAt"> = { offline: false, gapThreshold: 0.15, partyRule: "every_side" };

export const SNAPSHOT = "10 March 2025";
const SNAPSHOT_YEAR = 2025;
const AUSTLII_JUR: Record<string, string> = { Cth: "cth", NSW: "nsw", Vic: "vic", Qld: "qld", WA: "wa", SA: "sa",
  Tas: "tas", ACT: "act", NT: "nt" };

interface CourtYear { court: string; year: number; n: number; max: number; gap: number; src: string }
interface IndexA { as_at: string; url_prefix: Record<string, string>; court_years: CourtYear[] }
interface ShardA { court: string; year: number; max: number; gap: number; src: string; r: Record<string, [string, string, string]> }
interface IndexB { min_citing: number; series: { series: string; key: string; citations: number }[] }
interface ShardB { series: string; r: Record<string, [number, number, string[]]> }
interface StateAct { t: string; y: number | null; j: string; x: number; u: string }
interface CthAct { i: string; n: string; y: number | null; f: number; s: string; h: string[] }

/** Words that name the Crown, so "R v Smith" and "The Queen v Smith" meet. */
const CROWN_WORDS = ["queen", "king", "regina", "rex", "crown"];
let crownFps: Promise<Set<string>> | null = null;
const crown = () => (crownFps ??= Promise.all(CROWN_WORDS.map(fp)).then((xs) => new Set(xs)));

/** Do the parties written in a citation match a record's fingerprints (any of its variants)? */
export async function partiesMatch(parties: string, variants: string[], rule: Settings["partyRule"]): Promise<boolean> {
  const c = await crown();
  const sides = (await fingerprintSides(parties)).map((s) => s.filter((x) => !c.has(x))).filter((s) => s.length);
  if (!sides.length) return true; // nothing left to compare (e.g. "R v R")
  for (const v of variants) {
    const rec = new Set(decodeSides(v).flat().filter((x) => !c.has(x)));
    if (!rec.size) return true;
    const hit = sides.filter((s) => s.some((x) => rec.has(x))).length;
    if (rule === "every_side" ? hit === sides.length : hit > 0) return true;
  }
  return false;
}

const normTitle = (t: string) =>
  t.toLowerCase().replace(/\(no\.\s*/g, "(no ").replace(/[^a-z0-9() ]+/g, " ").replace(/\s+/g, " ").trim();

export class Checker {
  private memo = new Map<string, Promise<unknown>>();
  constructor(private loader: Loader, private settings: Settings) {}

  private load<T>(path: string, gz = true): Promise<T | null> {
    if (!this.memo.has(path)) this.memo.set(path, gz ? this.loader.gzJson<T>(path) : this.loader.json<T>(path));
    return this.memo.get(path) as Promise<T | null>;
  }

  async check(c: Citation): Promise<Result> {
    if (c.kind === "statute") return this.statute(c);
    return c.kind === "mnc" ? this.mnc(c) : this.report(c);
  }

  async checkAll(cs: Citation[]): Promise<Result[]> {
    return Promise.all(cs.map((c) => this.check(c)));
  }

  private result(citation: Citation, state: State, reason: string, extra: Partial<Result> = {}): Result {
    return { citation, state, reason, record: null, links: [], notes: [], ...extra };
  }

  private async mnc(c: CaseCitation): Promise<Result> {
    const court = c.court!;
    const name = COURTS.get(court)?.name;
    const links: Link[] = [];
    const jur = AUSTLII_JUR[COURTS.get(court)?.jurisdiction ?? ""];
    if (jur) links.push({ label: "AustLII", url: `https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/${jur}/${court}/${c.year}/${c.number}.html` });
    const idx = await this.load<IndexA>("a/index.json", false);
    const years = idx?.court_years.filter((x) => x.court === court) ?? [];
    if (!years.length) {
      return this.result(c, "CANNOT_CHECK", name
        ? `Decisions of the ${name} are not in the corpus, which covers the High Court, the Federal Court and NSW courts and tribunals.`
        : `"${court}" is not a court code this tool knows.`, { links });
    }
    if (c.year > SNAPSHOT_YEAR) {
      return this.result(c, "CANNOT_CHECK", `Decided after ${SNAPSHOT}, when the corpus stops.`, { links });
    }
    const cy = years.find((x) => x.year === c.year);
    if (!cy) return this.result(c, "CANNOT_CHECK", `No ${court} decisions from ${c.year} are in the corpus.`, { links });
    if (c.number! > cy.max) {
      return this.result(c, "CANNOT_CHECK", `The highest ${court} ${c.year} number in the corpus is ${cy.max}` +
        (c.year === SNAPSHOT_YEAR ? ` (the corpus stops on ${SNAPSHOT}).` : "."), { links });
    }
    const shard = await this.load<ShardA>(`a/${court}/${c.year}.json.gz`);
    const rec = shard?.r[String(c.number)];
    const pct = `${Math.round(cy.gap * 100)}%`;
    if (!rec) {
      if (cy.gap > this.settings.gapThreshold) {
        return this.result(c, "CANNOT_CHECK", `No ${court} ${c.year} decision numbered ${c.number} is in the corpus, but ` +
          `${pct} of that court-year's numbers are missing from it, so absence proves little.`, { links });
      }
      return this.result(c, "NO_RECORD", `No ${court} ${c.year} decision numbered ${c.number} is in the corpus. ` +
        `${pct} of that court-year's numbers are missing (possibly unpublished or restricted).`, { links });
    }
    const [date, tail, encoded] = rec;
    const url = (idx!.url_prefix[shard!.src] ?? "") + tail;
    const record = { date, url };
    links.unshift({ label: "Official copy (as at the corpus)", url });
    if (!c.parties) {
      return this.result(c, "FOUND", "A decision with this citation is in the corpus. No party names were given to compare.",
        { record, links });
    }
    if (!encoded) {
      return this.result(c, "FOUND", "A decision with this citation is in the corpus.", { record, links,
        notes: ["The record has no party names to compare."] });
    }
    return (await partiesMatch(c.parties, [encoded], this.settings.partyRule))
      ? this.result(c, "FOUND", "A decision with this citation is in the corpus, and the party names match.", { record, links })
      : this.result(c, "MISMATCH", "A decision with this citation is in the corpus, but its parties do not match the names given. " +
        "Open the official copy to see which case it is.", { record, links });
  }

  private async report(c: CaseCitation): Promise<Result> {
    const series = c.series!;
    const key = seriesKey(series);
    const idx = await this.load<IndexB>("b/index.json", false);
    if (!idx?.series.some((s) => s.key === key)) {
      return this.result(c, "CANNOT_CHECK", `${series} is not among the report series indexed.`);
    }
    const shard = await this.load<ShardB>(`b/${key}.json.gz`);
    const within = reportKey(series, c.year, c.volume, c.page!);
    const rec = shard?.r[within];
    if (!rec) {
      const square = findSeries(series)?.style === "square";
      const vols = Object.keys(shard?.r ?? {}).map((k) => Number(square ? k.split("|")[0]!.split("/")[0] : k.split("|")[0]));
      const top = Math.max(...vols.filter(Number.isFinite));
      const beyond = square ? c.year > top : (c.volume ?? 0) > top;
      if (beyond) {
        return this.result(c, "CANNOT_CHECK", `${square ? "The year" : "The volume"} is above the highest ${series} ` +
          `${square ? "year" : "volume"} cited in the corpus (${top}); the report may be newer than ${SNAPSHOT}.`);
      }
      return this.result(c, "NO_RECORD", `No judgment in the corpus cites this ${series} report. Only reports cited by ` +
        `at least ${idx.min_citing} judgments are indexed, so a real but rarely cited report can also land here.`);
    }
    const [n, usualYear, variants] = rec;
    const record = { citedBy: n, usualYear };
    const notes = findSeries(series)?.style === "round" && usualYear !== c.year
      ? [`Judgments usually cite this report with the year ${usualYear}.`] : [];
    if (!c.parties || !variants.length) {
      return this.result(c, "FOUND", `Cited by ${n} judgments in the corpus.` +
        (c.parties ? "" : " No party names were given to compare."), { record, notes });
    }
    return (await partiesMatch(c.parties, variants, this.settings.partyRule))
      ? this.result(c, "FOUND", `Cited by ${n} judgments in the corpus, under these party names.`, { record, notes })
      : this.result(c, "MISMATCH", `Cited by ${n} judgments in the corpus, but under different party names.`, { record, notes });
  }

  private async statute(s: StatuteCitation): Promise<Result> {
    const j = s.jurisdiction;
    if (j && !["Cth", "NSW", "Qld", "WA", "SA", "Tas"].includes(j)) {
      return this.result(s, "CANNOT_CHECK", `${j} legislation is not in this tool's sources (Commonwealth, NSW, Qld, WA, SA and Tas Acts only).`);
    }
    if (j === "Cth" || j === null) {
      const r = await this.cth(s);
      if (r.state !== "NO_RECORD" || j === "Cth") return r;
    }
    return this.stateAct(s);
  }

  private async cth(s: StatuteCitation): Promise<Result> {
    const acts = (await this.load<CthAct[]>("d/cth_acts.json.gz")) ?? [];
    const want = normTitle(s.title);
    const full = s.year ? normTitle(`${s.title} ${s.year}`) : null;
    const byName = (n: string) => normTitle(n) === full || (!full && normTitle(n).replace(/ \d{4}$/, "") === want);
    const pick = (xs: CthAct[]) => xs.find((a) => a.f) ?? xs[0]; // prefer the Act in force
    const current = acts.filter((a) => byName(a.n));
    let act = pick(current);
    let former: string | null = null;
    if (!act) {
      act = pick(acts.filter((a) => a.h.some(byName)));
      if (act) former = act.n;
    }
    const others = (former ? [] : current).filter((a) => a !== act);
    if (!act && full) {
      const sameTitle = acts.filter((a) => normTitle(a.n).replace(/ \d{4}$/, "") === want);
      if (sameTitle.length) {
        return this.result(s, "MISMATCH", `There is no ${s.title} ${s.year}; the Federal Register has ` +
          sameTitle.map((a) => a.n).join(", ") + ".", { record: { title: sameTitle[0]!.n } });
      }
    }
    if (!act) return this.result(s, "NO_RECORD", "No Commonwealth Act with this title is on the Federal Register (in force or repealed).");
    const url = `https://www.legislation.gov.au/${act.i}/latest/text`;
    const links = [{ label: "Federal Register of Legislation", url }];
    const notes: string[] = [];
    if (former) notes.push(`This is a former name; the Act is now called ${former}.`);
    if (others.length) notes.push(`Also on the Federal Register: ${others.map((a) => a.n).join(", ")}. Add the year to be sure.`);
    if (!act.f) notes.push(`Status on the Federal Register: ${act.s || "not in force"}.`);
    const record = { title: act.n, url };
    if (!s.provisions.length) return this.result(s, "FOUND", `${act.n} is on the Federal Register.`, { record, links, notes });
    if (this.settings.offline) {
      return this.result(s, "FOUND", `${act.n} is on the Federal Register. Section numbers were not checked (offline mode).`,
        { record, links, notes });
    }
    let list: SectionList | null = null;
    try {
      list = await fetchSections(act.i, this.settings.asAt, this.settings.fetchFn ?? fetch);
    } catch {
      list = null;
    }
    if (!list) {
      return this.result(s, "FOUND", `${act.n} is on the Federal Register, but its current text could not be read, ` +
        "so section numbers were not checked.", { record, links, notes });
    }
    const missing = s.provisions.filter((p) => {
      const set = p.schedule ? list!.schedules.get(p.schedule) : list!.body;
      return !set?.has(baseSection(p.section));
    });
    const where = (p: { schedule?: string; section: string }) => (p.schedule ? `sch ${p.schedule} s ${p.section}` : `s ${p.section}`);
    if (missing.length) {
      return this.result(s, "NO_RECORD", `${act.n} as in force on ${this.settings.asAt} (compilation ${list.registerId}) ` +
        `has no ${missing.map(where).join(", ")}. It may have been repealed or renumbered: check the version for the relevant date.`,
        { record, links, notes });
    }
    return this.result(s, "FOUND", `${act.n} as in force on ${this.settings.asAt} has ${s.provisions.map(where).join(", ")}.`,
      { record, links, notes });
  }

  private async stateAct(s: StatuteCitation): Promise<Result> {
    const acts = (await this.load<StateAct[]>("c/acts.json.gz")) ?? [];
    const want = normTitle(s.title);
    const hits = acts.filter((a) => a.j !== "Cth" && a.j !== "NI" && (!s.jurisdiction || a.j === s.jurisdiction) &&
      normTitle(a.t) === want && (!s.year || a.y === s.year));
    if (!hits.length) {
      return this.result(s, "CANNOT_CHECK", `No ${s.jurisdiction ?? "state"} Act with this title was in force at ${SNAPSHOT} ` +
        "in the corpus (repealed and later Acts are not in it).");
    }
    const a = hits[0]!;
    const url = a.u.startsWith("http") ? a.u : "";
    const notes = s.provisions.length ? ["Section numbers were not checked: the state sources here list titles only."] : [];
    if (hits.length > 1) notes.push(`More than one Act matches: ${hits.map((h) => `${h.t} ${h.y ?? ""} (${h.j})`).join("; ")}.`);
    if (a.x) notes.push("The source lists this Act as repealed.");
    return this.result(s, "FOUND", `${a.t} ${a.y ?? ""} (${a.j}) was in force at ${SNAPSHOT}.`, {
      record: { title: `${a.t} ${a.y ?? ""} (${a.j})`, url: url || undefined },
      links: url ? [{ label: "Official legislation site", url }] : [], notes,
    });
  }
}
