import json

from aic import ROOT
from aic.fingerprint import encode_title, fp, sides, words

VECTORS = json.loads((ROOT / "citecheck/tests/fingerprint_vectors.json").read_text())


def test_python_matches_the_committed_vectors():
    for v in VECTORS:
        if "word" in v:
            assert fp(v["word"]) == v["fp"]
            continue
        assert words(v["title"]) == v["words"]
        assert sides(v["title"]) == v["sides"]
        assert encode_title(v["title"]) == v["encoded"]


def test_no_readable_word_survives_encoding():
    enc = encode_title("Commissioner of Taxation v Hart")
    assert "hart" not in enc.lower() and "taxation" not in enc.lower()


def test_fingerprints_are_four_base64url_characters():
    assert all(len(fp(w)) == 4 and fp(w).replace("-", "").replace("_", "").isalnum() for w in ["a", "smith", "zz"])
