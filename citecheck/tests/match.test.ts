/**
 * Matcher tests against a small synthetic fixture index (brief: CI runs on fixtures, never on
 * the evaluation set). Every name and number here is made up for the test except well-known
 * authorities used only as strings.
 */
import { beforeAll, describe, expect, it } from "vitest";
import { fingerprintSides } from "../src/core/fingerprint.ts";
import { sectionsFromNcx, baseSection } from "../src/core/legislation.ts";
import { Checker, DEFAULTS, partiesMatch, type Loader, type Result } from "../src/core/match.ts";
import { parseCitations } from "../src/core/parse.ts";
import { readZipEntry } from "../src/core/zip.ts";

const enc = async (title: string) => (await fingerprintSides(title)).map((s) => s.join(" ")).join("|");

const files = new Map<string, unknown>();
const loader: Loader = {
  json: async <T>(p: string) => (files.get(p) as T) ?? null,
  gzJson: async <T>(p: string) => (files.get(p) as T) ?? null,
};

beforeAll(async () => {
  files.set("a/index.json", {
    as_at: "2025-03-10", url_prefix: { nsw_caselaw: "https://caselaw.example/decision/" },
    court_years: [
      { court: "NSWSC", year: 2019, n: 9, max: 10, gap: 0.1, src: "nsw_caselaw" },
      { court: "NSWLEC", year: 2019, n: 5, max: 10, gap: 0.5, src: "nsw_caselaw" },
      { court: "NSWSC", year: 2025, n: 3, max: 3, gap: 0, src: "nsw_caselaw" },
    ],
  });
  const recs: Record<string, [string, string, string]> = {};
  for (let n = 1; n <= 10; n++) if (n !== 4) recs[n] = ["2019-05-01", `id${n}`, await enc(`Party${n} v Other${n}`)];
  recs["7"] = ["2019-07-07", "id7", await enc("John Smith v Jane Jones (No 2)")];
  recs["8"] = ["2019-08-08", "id8", await enc("R v Brown")];
  recs["9"] = ["2019-09-09", "id9", ""];
  files.set("a/NSWSC/2019.json.gz", { court: "NSWSC", year: 2019, max: 10, gap: 0.1, src: "nsw_caselaw", r: recs });
  files.set("a/NSWLEC/2019.json.gz", { court: "NSWLEC", year: 2019, max: 10, gap: 0.5, src: "nsw_caselaw", r: { "1": ["", "x", ""] } });
  files.set("b/index.json", { min_citing: 2, series: [{ series: "CLR", key: "CLR", citations: 2 }, { series: "Qd R", key: "QDR", citations: 1 }] });
  files.set("b/CLR.json.gz", { series: "CLR", r: {
    "175|1": [500, 1992, [await enc("Mabo v Queensland (No 2)"), await enc("Mabo v Queensland")]],
    "200|5": [3, 1999, []],
  } });
  files.set("b/QDR.json.gz", { series: "Qd R", r: { "1990/1|5": [4, 1990, [await enc("Alpha v Beta")]] } });
  files.set("c/acts.json.gz", [
    { t: "Civil Liability Act", y: 2002, j: "NSW", x: 0, u: "https://legislation.example/nsw/cla" },
    { t: "Migration Act", y: 1958, j: "Cth", x: 0, u: "C2004A07412" },
  ]);
  files.set("d/cth_acts.json.gz", [
    { i: "C2004A00109", n: "Competition and Consumer Act 2010", y: 1974, f: 1, s: "In force", h: ["Trade Practices Act 1974"] },
    { i: "C2004A00818", n: "Corporations Act 2001", y: 2001, f: 1, s: "In force", h: [] },
    { i: "C1989A00109", n: "Corporations Act 1989", y: 1989, f: 0, s: "Repealed", h: [] },
    { i: "C1996A00086", n: "Workplace Relations Act 1996", y: 1996, f: 0, s: "Repealed", h: [] },
  ]);
});

// A stored (uncompressed) zip holding one file, for the fake Federal Register.
function storedZip(name: string, content: string): Uint8Array {
  const n = new TextEncoder().encode(name);
  const d = new TextEncoder().encode(content);
  const local = new Uint8Array(30 + n.length + d.length);
  const lv = new DataView(local.buffer);
  lv.setUint32(0, 0x04034b50, true); lv.setUint32(18, d.length, true); lv.setUint32(22, d.length, true);
  lv.setUint16(26, n.length, true); local.set(n, 30); local.set(d, 30 + n.length);
  const central = new Uint8Array(46 + n.length);
  const cv = new DataView(central.buffer);
  cv.setUint32(0, 0x02014b50, true); cv.setUint32(20, d.length, true); cv.setUint32(24, d.length, true);
  cv.setUint16(28, n.length, true); cv.setUint32(42, 0, true); central.set(n, 46);
  const end = new Uint8Array(22);
  const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, 1, true); ev.setUint16(10, 1, true);
  ev.setUint32(12, central.length, true); ev.setUint32(16, local.length, true);
  const out = new Uint8Array(local.length + central.length + end.length);
  out.set(local, 0); out.set(central, local.length); out.set(end, local.length + central.length);
  return out;
}
const NCX = `<ncx><navMap><navPoint><text>Part I—Preliminary</text></navPoint><navPoint><text>18  Meetings of Commission</text></navPoint>
<navPoint><text>45  Contracts</text></navPoint><navPoint><text>Schedule\u00a02—The Australian Consumer Law</text></navPoint>
<navPoint><text>18  Misleading or deceptive conduct</text></navPoint><navPoint><text>29  False representations</text></navPoint>
<navPoint><text>Endnotes</text></navPoint><navPoint><text>1  About the endnotes</text></navPoint></navMap></ncx>`;
const requests: string[] = [];
const fakeFetch = (async (url: string) => {
  requests.push(url);
  if (url.includes("/versions/find")) return new Response(JSON.stringify({ registerId: "C2026C00405", start: "2026-09-16T00:00:00" }));
  if (url.includes("/documents/find")) return new Response(new Blob([storedZip("OEBPS/document.ncx", NCX) as BlobPart]));
  return new Response("", { status: 404 });
}) as unknown as typeof fetch;

const settings = { ...DEFAULTS, asAt: "2026-10-26", fetchFn: fakeFetch };
async function check(text: string, over: Partial<typeof settings> = {}): Promise<Result> {
  const cs = parseCitations(text);
  expect(cs.length).toBeGreaterThan(0);
  return new Checker(loader, { ...settings, ...over }).check(cs[0]!);
}

describe("medium neutral citations", () => {
  it("FOUND when the parties match, ignoring first names and (No 2)", async () => {
    const r = await check("Smith v Jones [2019] NSWSC 7");
    expect(r.state).toBe("FOUND");
    expect(r.record?.url).toBe("https://caselaw.example/decision/id7");
  });
  it("MISMATCH when the parties differ", async () => {
    expect((await check("Smith v Taylor [2019] NSWSC 7")).state).toBe("MISMATCH");
  });
  it("FOUND for a bare citation, saying no names were compared", async () => {
    const r = await check("[2019] NSWSC 7");
    expect(r.state).toBe("FOUND");
    expect(r.reason).toMatch(/No party names/);
  });
  it("treats R and The Queen as the same party", async () => {
    expect((await check("The Queen v Brown [2019] NSWSC 8")).state).toBe("FOUND");
  });
  it("FOUND with a note when the record has no names", async () => {
    const r = await check("A v B [2019] NSWSC 9");
    expect(r.state).toBe("FOUND");
    expect(r.notes.join(" ")).toMatch(/no party names/);
  });
  it("NO_RECORD for a gap in a court-year with few gaps", async () => {
    const r = await check("Smith v Jones [2019] NSWSC 4");
    expect(r.state).toBe("NO_RECORD");
    expect(r.reason).toMatch(/10%/);
  });
  it("CANNOT_CHECK for a gap where too many numbers are missing", async () => {
    expect((await check("Smith v Jones [2019] NSWLEC 4")).state).toBe("CANNOT_CHECK");
  });
  it("the gap threshold is a setting", async () => {
    expect((await check("Smith v Jones [2019] NSWLEC 4", { gapThreshold: 0.6 })).state).toBe("NO_RECORD");
  });
  it("CANNOT_CHECK above the court-year maximum", async () => {
    const r = await check("Smith v Jones [2019] NSWSC 11");
    expect(r.state).toBe("CANNOT_CHECK");
    expect(r.reason).toMatch(/highest NSWSC 2019 number in the corpus is 10/);
  });
  it("CANNOT_CHECK after the snapshot", async () => {
    expect((await check("Smith v Jones [2026] NSWSC 1")).state).toBe("CANNOT_CHECK");
    expect((await check("Smith v Jones [2025] NSWSC 9")).reason).toMatch(/stops on 10 March 2025/);
  });
  it("CANNOT_CHECK for a court the corpus does not cover, naming it", async () => {
    const r = await check("Smith v Jones [2019] VSC 7");
    expect(r.state).toBe("CANNOT_CHECK");
    expect(r.reason).toMatch(/Supreme Court of Victoria/);
  });
  it("CANNOT_CHECK for an unknown code", async () => {
    expect((await check("Smith v Jones [2019] UKSC 7")).reason).toMatch(/not a court code/);
  });
  it("CANNOT_CHECK for a covered court in a year the corpus lacks", async () => {
    expect((await check("Smith v Jones [2018] NSWSC 7")).state).toBe("CANNOT_CHECK");
  });
  it("gives an AustLII link for a person to click", async () => {
    const r = await check("Smith v Jones [2019] NSWSC 7");
    expect(r.links.map((l) => l.url)).toContain("https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/nsw/NSWSC/2019/7.html");
  });
});

describe("law reports", () => {
  it("FOUND when cited under these parties", async () => {
    const r = await check("Mabo v Queensland (No 2) (1992) 175 CLR 1");
    expect(r.state).toBe("FOUND");
    expect(r.record?.citedBy).toBe(500);
  });
  it("MISMATCH under other parties", async () => {
    expect((await check("Smith v Jones (1992) 175 CLR 1")).state).toBe("MISMATCH");
  });
  it("notes an unusual year in a round-bracket series", async () => {
    expect((await check("Mabo v Queensland (1991) 175 CLR 1")).notes.join(" ")).toMatch(/1992/);
  });
  it("NO_RECORD for an uncited page within the volume range", async () => {
    expect((await check("Mabo v Queensland (1992) 175 CLR 2")).state).toBe("NO_RECORD");
  });
  it("CANNOT_CHECK above the highest volume cited", async () => {
    expect((await check("Smith v Jones (2030) 300 CLR 1")).state).toBe("CANNOT_CHECK");
  });
  it("square series: the year is part of the report", async () => {
    expect((await check("Alpha v Beta [1990] 1 Qd R 5")).state).toBe("FOUND");
    expect((await check("Alpha v Beta [1989] 1 Qd R 5")).state).toBe("NO_RECORD");
  });
  it("CANNOT_CHECK for a series not indexed", async () => {
    expect((await check("Smith v Jones [1990] 2 VR 1")).state).toBe("CANNOT_CHECK");
  });
  it("FOUND for a report with no names recorded", async () => {
    expect((await check("Smith v Jones (1999) 200 CLR 5")).state).toBe("FOUND");
  });
});

describe("Commonwealth Acts", () => {
  it("FOUND title and sections, from the current compilation", async () => {
    const r = await check("Competition and Consumer Act 2010 (Cth) s 45");
    expect(r.state).toBe("FOUND");
    expect(r.links[0]!.url).toBe("https://www.legislation.gov.au/C2004A00109/latest/text");
  });
  it("checks a schedule section in its schedule", async () => {
    expect((await check("Australian Consumer Law s 18")).state).toBe("FOUND");
    expect((await check("Australian Consumer Law s 45")).state).toBe("NO_RECORD");
  });
  it("NO_RECORD for a section that does not exist", async () => {
    const r = await check("Competition and Consumer Act 2010 (Cth) s 9999");
    expect(r.state).toBe("NO_RECORD");
    expect(r.reason).toMatch(/s 9999/);
  });
  it("FOUND by a former name, with a note", async () => {
    const r = await check("Trade Practices Act 1974 (Cth)");
    expect(r.state).toBe("FOUND");
    expect(r.notes.join(" ")).toMatch(/now called Competition and Consumer Act 2010/);
  });
  it("MISMATCH for the right title with the wrong year", async () => {
    expect((await check("Competition and Consumer Act 2011 (Cth)")).state).toBe("MISMATCH");
  });
  it("prefers the Act in force when the year is left out", async () => {
    const r = await check("Corporations Act s 1041H", { offline: true });
    expect(r.record?.title).toBe("Corporations Act 2001");
    expect(r.notes.join(" ")).toMatch(/Corporations Act 1989/);
  });
  it("FOUND with a repeal note", async () => {
    expect((await check("Workplace Relations Act 1996 (Cth)")).notes.join(" ")).toMatch(/Repealed/);
  });
  it("NO_RECORD for an unknown Commonwealth title", async () => {
    expect((await check("Imaginary Things Act 2019 (Cth)")).state).toBe("NO_RECORD");
  });
  it("offline mode: no request leaves, sections are not checked", async () => {
    requests.length = 0;
    const r = await check("Competition and Consumer Act 2010 (Cth) s 9999", { offline: true });
    expect(r.state).toBe("FOUND");
    expect(r.reason).toMatch(/offline/);
    expect(requests).toEqual([]);
  });
  it("online: sends only the register id and date, never document text", async () => {
    requests.length = 0;
    await new Checker(loader, { ...settings, asAt: "2026-10-27" }).check(parseCitations("Corporations Act 2001 (Cth) s 180")[0]!);
    expect(requests.every((u) => u.startsWith("https://api.prod.legislation.gov.au/v1/"))).toBe(true);
    expect(requests.join(" ")).not.toMatch(/180|Corporations/);
  });
});

describe("state Acts", () => {
  it("FOUND in force at the snapshot, sections not checked", async () => {
    const r = await check("Civil Liability Act 2002 (NSW) s 5B");
    expect(r.state).toBe("FOUND");
    expect(r.notes.join(" ")).toMatch(/not checked/);
  });
  it("CANNOT_CHECK when a state Act is not found", async () => {
    expect((await check("Imaginary Things Act 2019 (NSW)")).state).toBe("CANNOT_CHECK");
  });
  it("CANNOT_CHECK for Victorian legislation", async () => {
    const r = await check("Charter of Human Rights and Responsibilities Act 2006 (Vic) s 32");
    expect(r.state).toBe("CANNOT_CHECK");
    expect(r.reason).toMatch(/Vic legislation/);
  });
  it("falls back to state titles when the jurisdiction is left out", async () => {
    expect((await check("Civil Liability Act 2002 s 5B")).state).toBe("FOUND");
  });
});

describe("helpers", () => {
  it("partiesMatch: every side vs any side", async () => {
    const rec = [await enc("Smith v Jones")];
    expect(await partiesMatch("Smith v Brown", rec, "every_side")).toBe(false);
    expect(await partiesMatch("Smith v Brown", rec, "any_side")).toBe(true);
  });
  it("sectionsFromNcx stops at the endnotes and files schedules separately", () => {
    const s = sectionsFromNcx(NCX);
    expect([...s.body]).toEqual(["18", "45"]);
    expect([...s.schedules.get("2")!]).toEqual(["18", "29"]);
  });
  it("baseSection", () => {
    expect(baseSection("52(1)(a)")).toBe("52");
    expect(baseSection("1041H(1)")).toBe("1041H");
  });
  it("readZipEntry reads a stored entry and returns null when absent", async () => {
    const z = storedZip("OEBPS/document.ncx", "hello");
    expect(new TextDecoder().decode((await readZipEntry(z, "document.ncx"))!)).toBe("hello");
    expect(await readZipEntry(z, "missing.txt")).toBeNull();
  });
});
