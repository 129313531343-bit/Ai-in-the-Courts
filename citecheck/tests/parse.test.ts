import { describe, expect, it } from "vitest";
import { COURTS, normaliseChars, parseCitations, partiesBefore } from "../src/core/parse.ts";
import { SERIES, findSeries, seriesKey } from "../src/core/series.ts";
import type { CaseCitation, StatuteCitation } from "../src/core/types.ts";

const cases = (text: string) => parseCitations(text).filter((c): c is CaseCitation => c.kind !== "statute");
const statutes = (text: string) => parseCitations(text).filter((c): c is StatuteCitation => c.kind === "statute");
function one(text: string): CaseCitation {
  const found = cases(text);
  expect(found).toHaveLength(1);
  return found[0]!;
}
function act(text: string): StatuteCitation {
  const found = statutes(text);
  expect(found).toHaveLength(1);
  return found[0]!;
}

describe("medium neutral citations", () => {
  const mncs: [string, string, number, number][] = [
    ["[2019] NSWSC 123", "NSWSC", 2019, 123],
    ["[2008] HCA 36", "HCA", 2008, 36],
    ["[2021] FCAFC 7", "FCAFC", 2021, 7],
    ["[2024] FedCFamC2G 1245", "FedCFamC2G", 2024, 1245],
    ["[2025] NSWCATAD 12", "NSWCATAD", 2025, 12],
    ["[2023] VSCA 300", "VSCA", 2023, 300],
    ["[2022] QCA 4", "QCA", 2022, 4],
    ["[2020] WASC 99", "WASC", 2020, 99],
    ["[2018] NSWCCA 1", "NSWCCA", 2018, 1],
    ["[2017] NSWLEC 150", "NSWLEC", 2017, 150],
    ["[2026] ARTA 10", "ARTA", 2026, 10],
    ["[1999] FCA 1", "FCA", 1999, 1],
  ];
  for (const [text, court, year, number] of mncs) {
    it(`reads ${text}`, () => {
      const c = one(`See ${text}.`);
      expect(c).toMatchObject({ kind: "mnc", court, year, number, parties: null, pinpoint: null });
    });
  }
  it("tolerates spaces inside the brackets", () => {
    expect(one("[ 2024] VSCA 264")).toMatchObject({ year: 2024, court: "VSCA", number: 264 });
  });
  it("reads an unknown court code as an MNC (checked later)", () => {
    expect(one("[2019] UKSC 5")).toMatchObject({ kind: "mnc", court: "UKSC", number: 5 });
  });
  it("does not read a year range or a bare year", () => {
    expect(cases("In 2019 the NSWSC sat 123 days.")).toHaveLength(0);
  });
  it("does not run the number into following digits", () => {
    expect(one("[2019] NSWSC 1234 and more")).toMatchObject({ number: 1234 });
  });
  it("finds several in one sentence", () => {
    const found = cases("See [2019] NSWSC 1, [2020] NSWCA 2 and [2021] HCA 3.");
    expect(found.map((c) => c.number)).toEqual([1, 2, 3]);
  });
});

describe("MNC pinpoints", () => {
  const pins: [string, string][] = [
    ["[2019] NSWSC 123 at [45]", "[45]"],
    ["[2019] NSWSC 123, [45]", "[45]"],
    ["[2019] NSWSC 123 [45]", "[45]"],
    ["[2019] NSWSC 123 at [45]-[47]", "[45]-[47]"],
    ["[2019] NSWSC 123 at [45]–[47]", "[45]-[47]"],
    ["[2019] NSWSC 123 at [45], [50]", "[45], [50]"],
    ["[2019] NSWSC 123 at [45] and [50]", "[45] and [50]"],
  ];
  for (const [text, pin] of pins) {
    it(`reads the pinpoint in ${text}`, () => {
      expect(one(text).pinpoint).toBe(pin);
    });
  }
  it("keeps the original dash in raw", () => {
    expect(one("[2019] NSWSC 123 at [45]–[47]").raw).toBe("[2019] NSWSC 123 at [45]–[47]");
  });
});

describe("law report citations", () => {
  const reports: [string, string, number | null, number, "round" | "square"][] = [
    ["(1992) 175 CLR 1", "CLR", 175, 1, "round"],
    ["(2003) 214 CLR 269", "CLR", 214, 269, "round"],
    ["(2019) 368 ALR 390", "ALR", 368, 390, "round"],
    ["(2004) 78 ALJR 1", "ALJR", 78, 1, "round"],
    ["(1995) 59 FCR 1", "FCR", 59, 1, "round"],
    ["(1987) 10 NSWLR 86", "NSWLR", 10, 86, "round"],
    ["[1990] 1 Qd R 5", "Qd R", 1, 5, "square"],
    ["[1990] VR 1", "VR", null, 1, "square"],
    ["[1999] 2 VR 300", "VR", 2, 300, "square"],
    ["(1998) 20 WAR 1", "WAR", 20, 1, "round"],
    ["(2001) 80 SASR 1", "SASR", 80, 1, "round"],
    ["(1950) 50 SR (NSW) 1", "SR (NSW)", 50, 1, "round"],
    ["(2000) 26 Fam LR 1", "Fam LR", 26, 1, "round"],
    ["(1994) 72 A Crim R 1", "A Crim R", 72, 1, "round"],
    ["[1932] AC 562", "AC", null, 562, "square"],
    ["[1990] 1 WLR 1", "WLR", 1, 1, "square"],
    ["[1999] 2 All ER 1", "All ER", 2, 1, "square"],
    ["[1990] 1 NZLR 1", "NZLR", 1, 1, "square"],
    ["(2005) 63 IPR 1", "IPR", 63, 1, "round"],
    ["(1999) 104 LGERA 1", "LGERA", 104, 1, "round"],
  ];
  for (const [text, series, volume, page, bracket] of reports) {
    it(`reads ${text}`, () => {
      expect(one(`See ${text}.`)).toMatchObject({ kind: "report", series, volume, page, bracket });
    });
  }
  it("accepts the series without the space ('QdR')", () => {
    expect(one("[1990] 1 QdR 5")).toMatchObject({ series: "Qd R" });
  });
  it("accepts full stops in the series ('C.L.R.')", () => {
    expect(one("(1992) 175 C.L.R. 1")).toMatchObject({ series: "CLR", page: 1 });
  });
  it("accepts a year range", () => {
    expect(one("(1990-91) 170 CLR 1")).toMatchObject({ year: 1990, volume: 170 });
  });
  it("records the bracket actually used, even when it is the wrong one", () => {
    expect(one("[1992] 175 CLR 1")).toMatchObject({ bracket: "square", series: "CLR" });
  });
  it("ignores unknown series", () => {
    expect(cases("(1992) 175 XYZ 1")).toHaveLength(0);
  });
  it("does not read a date as a report", () => {
    expect(cases("(2019) 12 March")).toHaveLength(0);
  });
  it("does not read [1990] VR 1 as an MNC", () => {
    expect(cases("[1990] VR 1")).toHaveLength(1);
  });
});

describe("report pinpoints", () => {
  const pins: [string, string | null][] = [
    ["(1992) 175 CLR 1, 15", "15"],
    ["(1992) 175 CLR 1 at 15", "15"],
    ["(1992) 175 CLR 1, 15-16", "15-16"],
    ["(1992) 175 CLR 1, 15, 20", "15, 20"],
    ["(1992) 175 CLR 1, 15 [30]", "15 [30]"],
    ["(1992) 175 CLR 1 15", null],
  ];
  for (const [text, pin] of pins) {
    it(`pinpoint of ${text}`, () => {
      expect(one(text).pinpoint).toBe(pin);
    });
  }
});

describe("party names", () => {
  const named: [string, string][] = [
    ["Smith v Jones [2019] NSWSC 123", "Smith v Jones"],
    ["See Smith v Jones [2019] NSWSC 123", "Smith v Jones"],
    ["see Smith v Jones [2019] NSWSC 123", "Smith v Jones"],
    ["In Smith v Jones [2019] NSWSC 123", "Smith v Jones"],
    ["as held in Smith v Jones [2019] NSWSC 123", "Smith v Jones"],
    ["R v Smith [2019] NSWCCA 1", "R v Smith"],
    ["The Queen v Smith [2019] HCA 1", "The Queen v Smith"],
    ["Mabo v Queensland (No 2) (1992) 175 CLR 1", "Mabo v Queensland (No 2)"],
    ["Commissioner of Taxation v Hart (2004) 217 CLR 216", "Commissioner of Taxation v Hart"],
    ["Minister for Immigration and Border Protection v SZMTA (2019) 264 CLR 421",
      "Minister for Immigration and Border Protection v SZMTA"],
    ["Re Wakim; Ex parte McNally (1999) 198 CLR 511", "Re Wakim; Ex parte McNally"],
    ["Re Smith [2019] NSWSC 1", "Re Smith"],
    ["Attorney-General (NSW) v Quin (1990) 170 CLR 1", "Attorney-General (NSW) v Quin"],
    ["BHP Billiton Ltd v Schultz (2004) 221 CLR 400", "BHP Billiton Ltd v Schultz"],
    ["Plaintiff M70/2011 v Minister for Immigration and Citizenship (2011) 244 CLR 144",
      "Plaintiff M70/2011 v Minister for Immigration and Citizenship"],
    ["Donoghue v Stevenson [1932] AC 562", "Donoghue v Stevenson"],
    ["Hockey v Fairfax Media Publications Pty Limited [2015] FCA 652", "Hockey v Fairfax Media Publications Pty Limited"],
    ["Council of the City of Sydney v Smith [2019] NSWLEC 1", "Council of the City of Sydney v Smith"],
    ["In the Marriage of Smith (1990) 14 Fam LR 1", "In the Marriage of Smith"],
    ["Smith v Jones Pty Ltd [2019] NSWSC 1", "Smith v Jones Pty Ltd"],
    ["Smith v Jones & Co [2019] NSWSC 1", "Smith v Jones & Co"],
    ["Smith v. Jones [2019] NSWSC 1", "Smith v. Jones"],
    ["Following Smith v Jones [2019] NSWSC 1", "Smith v Jones"],
  ];
  for (const [text, parties] of named) {
    it(`finds the parties in "${text}"`, () => {
      expect(one(text).parties).toBe(parties);
    });
  }
  it("raw starts at the parties", () => {
    expect(one("as held in Smith v Jones [2019] NSWSC 123 at [4].").raw).toBe("Smith v Jones [2019] NSWSC 123 at [4]");
  });
  it("leaves a bare citation without parties", () => {
    expect(one("the court said so: [2019] NSWSC 123").parties).toBeNull();
  });
  it("does not take words from the previous sentence", () => {
    expect(one("This was Brown v Green. Smith v Jones [2019] NSWSC 1").parties).toBe("Smith v Jones");
  });
  it("needs a 'v' or a Re form", () => {
    expect(one("Justice Smith [2019] NSWSC 1").parties).toBeNull();
  });
  it("stops at a comma", () => {
    expect(one("Brown, Smith v Jones [2019] NSWSC 1").parties).toBe("Smith v Jones");
  });
  it("copies the parties to a parallel citation after a semicolon", () => {
    const [a, b] = cases("Smith v Jones (2008) 236 CLR 573; [2008] HCA 36");
    expect(a!.parties).toBe("Smith v Jones");
    expect(b).toMatchObject({ kind: "mnc", court: "HCA", parties: "Smith v Jones" });
  });
  it("copies the parties to a parallel citation after a comma", () => {
    const [, b] = cases("Smith v Jones (2008) 236 CLR 573, [2008] HCA 36");
    expect(b!.parties).toBe("Smith v Jones");
  });
  it("does not copy parties across other words", () => {
    const [, b] = cases("Smith v Jones (2008) 236 CLR 573 and later [2009] HCA 1");
    expect(b!.parties).toBeNull();
  });
  it("gives each of two cited cases its own parties", () => {
    const found = cases("Smith v Jones [2019] NSWSC 1; Brown v Green [2020] NSWCA 2");
    expect(found.map((c) => c.parties)).toEqual(["Smith v Jones", "Brown v Green"]);
  });
  it("partiesBefore needs the name to touch the citation", () => {
    const text = "Smith v Jones, [2019] NSWSC 1";
    expect(partiesBefore(normaliseChars(text), text.indexOf("["))).toBeNull();
  });
});

describe("statutes", () => {
  it("reads title, year and jurisdiction", () => {
    expect(act("the Competition and Consumer Act 2010 (Cth)")).toMatchObject({
      title: "Competition and Consumer Act", year: 2010, jurisdiction: "Cth", provisions: [],
    });
  });
  it("reads a section after the Act", () => {
    expect(act("Migration Act 1958 (Cth) s 501").provisions).toEqual([{ section: "501" }]);
  });
  it("reads a section with a comma", () => {
    expect(act("Evidence Act 1995 (NSW), s 135").provisions).toEqual([{ section: "135" }]);
  });
  it("reads subsections", () => {
    expect(act("Corporations Act 2001 (Cth) s 1041H(1)").provisions).toEqual([{ section: "1041H(1)" }]);
  });
  it("reads paragraph-level references", () => {
    expect(act("Fair Work Act 2009 (Cth) s 394(2)(a)").provisions).toEqual([{ section: "394(2)(a)" }]);
  });
  it("reads ss with a range", () => {
    expect(act("Civil Procedure Act 2005 (NSW) ss 56-58").provisions.map((p) => p.section)).toEqual(["56", "58"]);
  });
  it("reads ss with 'and'", () => {
    expect(act("Civil Procedure Act 2005 (NSW) ss 56 and 59").provisions.map((p) => p.section)).toEqual(["56", "59"]);
  });
  it("reads a schedule and section after the Act", () => {
    expect(act("Competition and Consumer Act 2010 (Cth) sch 2 s 18").provisions).toEqual([{ schedule: "2", section: "18" }]);
  });
  it("reads 'Schedule 2, s 18'", () => {
    expect(act("Competition and Consumer Act 2010 (Cth) Schedule 2, s 18").provisions).toEqual([{ schedule: "2", section: "18" }]);
  });
  it("reads a section before the Act", () => {
    const a = act("s 501 of the Migration Act 1958 (Cth)");
    expect(a).toMatchObject({ title: "Migration Act", year: 1958 });
    expect(a.provisions).toEqual([{ section: "501" }]);
  });
  it("reads 'section 18 of the ...'", () => {
    expect(act("section 18 of the Competition and Consumer Act 2010").provisions).toEqual([{ section: "18" }]);
  });
  it("reads 's 18 of sch 2 to the ...'", () => {
    expect(act("s 18 of sch 2 to the Competition and Consumer Act 2010 (Cth)").provisions).toEqual([
      { schedule: "2", section: "18" },
    ]);
  });
  it("records an omitted jurisdiction as null", () => {
    expect(act("Corporations Act 2001 s 180").jurisdiction).toBeNull();
  });
  it("reads an Act with a bracketed part of its title", () => {
    expect(act("Crimes (Sentencing Procedure) Act 1999 (NSW) s 21A")).toMatchObject({
      title: "Crimes (Sentencing Procedure) Act", year: 1999, jurisdiction: "NSW",
    });
  });
  it("reads a long title with connectors", () => {
    expect(act("Australian Securities and Investments Commission Act 2001 (Cth) s 12DA").title).toBe(
      "Australian Securities and Investments Commission Act",
    );
  });
  it("reads 'A New Tax System (Goods and Services Tax) Act 1999'", () => {
    expect(act("A New Tax System (Goods and Services Tax) Act 1999 (Cth) s 9-5").title).toBe(
      "A New Tax System (Goods and Services Tax) Act",
    );
  });
  it("trims a lead-in word", () => {
    expect(act("Under the Migration Act 1958 (Cth) s 501").title).toBe("Migration Act");
  });
  it("trims 'Section 18 of the' into a provision", () => {
    const a = act("Section 18 of the Competition and Consumer Act 2010 (Cth)");
    expect(a.title).toBe("Competition and Consumer Act");
    expect(a.provisions).toEqual([{ section: "18" }]);
  });
  it("trims a sentence-initial 'The'", () => {
    expect(act("The Migration Act 1958 (Cth) applies.").title).toBe("Migration Act");
  });
  it("reads an Act without a year when a section is given", () => {
    expect(act("Corporations Act s 1041H")).toMatchObject({ title: "Corporations Act", year: null });
  });
  it("ignores an Act without a year or section", () => {
    expect(statutes("the Corporations Act requires it")).toHaveLength(0);
  });
  it("ignores 'the Act'", () => {
    expect(statutes("s 5 of the Act")).toHaveLength(0);
  });
  it("reads two Acts in one sentence", () => {
    const found = statutes("the Family Law Act 1975 (Cth) and the Child Support (Assessment) Act 1989 (Cth)");
    expect(found.map((s) => s.title)).toEqual(["Family Law Act", "Child Support (Assessment) Act"]);
  });
  it("reads 'Acts Interpretation Act 1901'", () => {
    expect(act("Acts Interpretation Act 1901 (Cth) s 15AA").title).toBe("Acts Interpretation Act");
  });
  it("reads a state Act", () => {
    expect(act("Civil Liability Act 2002 (NSW) s 5B")).toMatchObject({ jurisdiction: "NSW", provisions: [{ section: "5B" }] });
  });
  it("reads a Victorian Act", () => {
    expect(act("Charter of Human Rights and Responsibilities Act 2006 (Vic) s 32").jurisdiction).toBe("Vic");
  });
  it("reads 's.' with a full stop", () => {
    expect(act("Migration Act 1958 (Cth) s. 501").provisions).toEqual([{ section: "501" }]);
  });
  it("keeps the original text in raw", () => {
    expect(act("see s 501 of the Migration Act 1958 (Cth).").raw).toBe("s 501 of the Migration Act 1958 (Cth)");
  });
});

describe("Australian Consumer Law", () => {
  it("reads 'Australian Consumer Law s 18' as sch 2 of the CCA", () => {
    expect(act("Australian Consumer Law s 18")).toMatchObject({
      title: "Competition and Consumer Act", year: 2010, jurisdiction: "Cth", alias: "Australian Consumer Law",
      provisions: [{ schedule: "2", section: "18" }],
    });
  });
  it("reads 's 18 of the Australian Consumer Law'", () => {
    expect(act("s 18 of the Australian Consumer Law").provisions).toEqual([{ schedule: "2", section: "18" }]);
  });
  it("reads 'ACL s 18'", () => {
    expect(act("ACL s 18").provisions).toEqual([{ schedule: "2", section: "18" }]);
  });
  it("ignores 'ACL' without a section", () => {
    expect(statutes("a ruptured ACL in 2019")).toHaveLength(0);
  });
  it("reads the state application '(NSW)'", () => {
    expect(act("Australian Consumer Law (NSW) s 18").jurisdiction).toBe("NSW");
  });
  it("reads 'Australian Consumer Law' with no section", () => {
    expect(act("the Australian Consumer Law applies").provisions).toEqual([]);
  });
});

describe("mixed text", () => {
  const text =
    "In Smith v Jones [2019] NSWSC 123 at [45], the Court applied s 18 of the Australian Consumer Law and " +
    "Mabo v Queensland (No 2) (1992) 175 CLR 1, 15; [1992] HCA 23. See also Migration Act 1958 (Cth) s 501.";
  const found = parseCitations(text);
  it("finds all five in order", () => {
    expect(found.map((c) => c.kind)).toEqual(["mnc", "statute", "report", "mnc", "statute"]);
  });
  it("offsets point back into the text", () => {
    for (const c of found) expect(text.slice(c.start, c.end).trim()).toBe(c.raw);
  });
  it("does not read a case name as an Act", () => {
    expect(statutes("Smith v Commonwealth Bank Act [2019] NSWSC 1")).toHaveLength(0);
  });
  it("handles curly quotes and non-breaking spaces", () => {
    expect(one("O’Brien v Smith [2019] NSWSC 1")).toMatchObject({ parties: "O’Brien v Smith", number: 1 });
  });
  it("handles a line break inside a citation", () => {
    expect(one("Smith v Jones [2019]\nNSWSC 1")).toMatchObject({ court: "NSWSC", number: 1 });
  });
  it("returns nothing for plain text", () => {
    expect(parseCitations("Nothing to see here, 2019, section five.")).toEqual([]);
  });
});

describe("tables", () => {
  it("knows the main courts", () => {
    for (const code of ["HCA", "FCA", "FCAFC", "NSWSC", "NSWCA", "VSC", "QSC", "WASC"]) expect(COURTS.has(code)).toBe(true);
  });
  it("series keys ignore spacing and case", () => {
    expect(seriesKey("Qd R")).toBe(seriesKey("QD R"));
    expect(findSeries("qdr")?.abbr).toBe("Qd R");
  });
  it("series abbreviations are unique", () => {
    expect(new Set(SERIES.map((s) => seriesKey(s.abbr))).size).toBe(SERIES.length);
  });
  it("normaliseChars keeps the length", () => {
    const s = "‘a’ – “b”  c\n";
    expect(normaliseChars(s)).toHaveLength(s.length);
  });
});
