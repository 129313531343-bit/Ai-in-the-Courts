/**
 * Index (b): law report citation -> how the citing judgments name the parties, and how many
 * judgments cite it. Mined from the corpus's judgment text with the shipped parser
 * (src/core/parse.ts), so the index keys are exactly what the site will look up.
 *
 * Brief: keep only citations made by at least 2 judgments, and EXCLUDE every evaluation
 * source document (eval/eval_sources.csv, reserved before mining; DECISIONS.md D032).
 * Party names are kept only as fingerprints (D031, E1).
 *
 * Usage: node citecheck/scripts/mine_reports.ts [--limit N]   (full runs also write data/interim/index_b_mining.json)
 * Output (gitignored, local only): cache/corpus/reports_raw.json, aggregated per citation:
 *   { "<series>|<volume>|<page>": { n, years: {year: count}, parties: {encoded: count}, names: {written: count} } }
 * "names" keeps the party names as written, for the evaluation's ground truth on this machine;
 * the public index is built from the fingerprints alone (scripts/25_build_index_b.py).
 */
import { createHash } from "node:crypto";
import { createReadStream, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { parseCitations } from "../src/core/parse.ts";
import { sides } from "../src/core/fingerprint.ts";
import type { CaseCitation } from "../src/core/types.ts";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const limitArg = process.argv.indexOf("--limit");
const LIMIT = limitArg > 0 ? Number(process.argv[limitArg + 1]) : Infinity;

// Same algorithm as fingerprint.ts fp(), synchronous for speed; checked against the vectors below.
const fpSync = (w: string) => createHash("sha256").update(w).digest().subarray(0, 3).toString("base64url");
const encode = (parties: string) => sides(parties).map((s) => s.map(fpSync).join(" ")).join("|");
for (const v of JSON.parse(readFileSync(`${ROOT}citecheck/tests/fingerprint_vectors.json`, "utf8"))) {
  if (v.word && fpSync(v.word) !== v.fp) throw new Error("fpSync disagrees with the fingerprint vectors");
  if (v.title !== undefined && encode(v.title) !== v.encoded) throw new Error(`encode disagrees for ${v.title}`);
}

const evalIds = new Set(
  readFileSync(`${ROOT}eval/eval_sources.csv`, "utf8").trim().split("\n").slice(1).map((l) => l.split(",")[0]),
);

interface Entry { n: number; years: Record<string, number>; parties: Record<string, number>; names: Record<string, number> }
const index = new Map<string, Entry>();
let docs = 0;
let skippedEval = 0;
let cites = 0;
const started = Date.now();

const lines = createInterface({ input: createReadStream(`${ROOT}cache/corpus/corpus.jsonl`), crlfDelay: Infinity });
for await (const line of lines) {
  const d = JSON.parse(line) as { version_id: string; type: string; text: string | null };
  if (d.type !== "decision") continue;
  if (evalIds.has(d.version_id)) { skippedEval++; continue; }
  if (++docs > LIMIT) break;
  const seenHere = new Set<string>();
  for (const c of parseCitations(d.text ?? "")) {
    if (c.kind !== "report") continue;
    const r = c as CaseCitation;
    const key = `${r.series}|${r.volume ?? ""}|${r.page}`;
    cites++;
    let e = index.get(key);
    if (!e) index.set(key, (e = { n: 0, years: {}, parties: {}, names: {} }));
    if (!seenHere.has(key)) { e.n++; seenHere.add(key); }
    e.years[r.year] = (e.years[r.year] ?? 0) + 1;
    if (r.parties) {
      const enc = encode(r.parties);
      if (enc) e.parties[enc] = (e.parties[enc] ?? 0) + 1;
      if (Object.keys(e.names).length < 20 || e.names[r.parties]) e.names[r.parties] = (e.names[r.parties] ?? 0) + 1;
    }
  }
  if (docs % 10000 === 0) console.log(`${docs.toLocaleString()} judgments, ${index.size.toLocaleString()} citations, ${((Date.now() - started) / 1000).toFixed(0)} s`);
}
writeFileSync(`${ROOT}cache/corpus/reports_raw.json`, JSON.stringify(Object.fromEntries(index)));
const stats = { judgments: Math.min(docs, LIMIT), eval_sources_skipped: skippedEval, report_citations: cites,
  distinct: index.size, cited_by_2_plus: [...index.values()].filter((e) => e.n >= 2).length,
  seconds: Math.round((Date.now() - started) / 1000) };
if (LIMIT === Infinity) writeFileSync(`${ROOT}data/interim/index_b_mining.json`, JSON.stringify(stats, null, 1) + "\n");
console.log(JSON.stringify(stats));
