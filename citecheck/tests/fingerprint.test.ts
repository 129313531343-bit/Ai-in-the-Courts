import { describe, expect, it } from "vitest";
import vectors from "./fingerprint_vectors.json" with { type: "json" };
import { decodeSides, fingerprintSides, fp, sides, words } from "../src/core/fingerprint.ts";

type TitleVector = { title: string; words: string[]; sides: string[][]; encoded: string };
type WordVector = { word: string; fp: string };
const titles = (vectors as (TitleVector | WordVector)[]).filter((v): v is TitleVector => "title" in v);
const wordVecs = (vectors as (TitleVector | WordVector)[]).filter((v): v is WordVector => "word" in v);

describe("fingerprints agree with the Python build (aic/fingerprint.py)", () => {
  for (const v of titles) {
    it(`same words, sides and encoding for "${v.title}"`, async () => {
      expect(words(v.title)).toEqual(v.words);
      expect(sides(v.title)).toEqual(v.sides);
      const enc = (await fingerprintSides(v.title)).map((s) => s.join(" ")).join("|");
      expect(enc).toBe(v.encoded);
      expect(decodeSides(v.encoded)).toEqual(await fingerprintSides(v.title));
    });
  }
  for (const v of wordVecs) {
    it(`fp("${v.word}")`, async () => {
      expect(await fp(v.word)).toBe(v.fp);
    });
  }
});
