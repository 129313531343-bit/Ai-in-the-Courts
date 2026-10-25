import aic.spend as spend


def test_usage_cost_batch_discount():
    # 1M input + 100k output on Opus 5.5 at batch (50%) rates: (4 + 2) / 2 = 3.00
    assert round(spend.usage_cost("claude-opus-5-5", {"input_tokens": 1_000_000, "output_tokens": 100_000}), 4) == 3.0


def test_budget_guard_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr(spend, "LOG", tmp_path / "spend_log.csv")
    monkeypatch.setattr(spend, "pending", lambda: 0.0)
    assert spend.spent() == 0 and spend.check_budget(29.99) is None
    spend.record("b1", "04_pass_a", "claude-opus-5-5", [{"input_tokens": 5_000_000, "output_tokens": 500_000}])
    assert round(spend.spent(), 2) == 15.0
    spend.record("b1", "04_pass_a", "claude-opus-5-5", [{"input_tokens": 5_000_000, "output_tokens": 500_000}])
    assert round(spend.spent(), 2) == 15.0  # re-collecting a batch replaces its entry
    assert spend.check_budget(15.01) is not None and spend.check_budget(14.99) is None


def test_in_flight_batches_count(tmp_path, monkeypatch):
    monkeypatch.setattr(spend, "LOG", tmp_path / "spend_log.csv")
    monkeypatch.setattr(spend, "pending", lambda: 20.0)
    assert spend.check_budget(10.01) is not None and spend.check_budget(9.99) is None
