"""Testes do ciclo de vida dos anúncios (novo / retirado / preço) e do mercado demo vivo."""
import pandas as pd

from src.data_ingestion.demo_data import evolve_synthetic_listings, generate_synthetic_listings
from src.data_processing.cleaner import DataCleaner
from src.data_processing.lifecycle import diff_listings, lifecycle_alerts, listing_key
from src.data_processing.serialization import df_to_records

DB_COLS = ["source", "source_id", "price", "area", "rooms", "bedrooms", "bathrooms", "address",
           "city", "state", "neighborhood", "latitude", "longitude", "url", "scraped_at"]


def _frame(rows):
    return pd.DataFrame(rows, columns=["source", "source_id", "city", "neighborhood", "price"])


class TestListingKey:
    def test_prefers_source_and_id_then_url_then_address(self):
        df = pd.DataFrame(
            {
                "source": ["a", "a", None, None],
                "source_id": ["1", "nan", None, None],
                "url": ["u0", "u1", "u2", None],
                "address": ["x", "y", "z", "w"],
            }
        )
        assert list(listing_key(df)) == ["a|1", "u1", "u2", "w"]


class TestDiff:
    def test_detects_new_removed_and_price_changes(self):
        prev = _frame([("s", "1", "SP", "A", 100.0), ("s", "2", "SP", "A", 200.0),
                       ("s", "3", "SP", "B", 300.0), ("s", "4", "SP", "B", 400.0)])
        cur = _frame([("s", "1", "SP", "A", 100.0),   # igual
                      ("s", "2", "SP", "A", 180.0),   # −10%
                      ("s", "3", "SP", "B", 330.0),   # +10%
                      ("s", "5", "SP", "C", 500.0)])  # novo (e o 4 saiu)
        d = diff_listings(prev, cur)
        assert d.counts() == {"new": 1, "removed": 1, "price_drops": 1, "price_increases": 1,
                              "unchanged": 1, "ignored_large_changes": 0}
        assert list(d.new["source_id"]) == ["5"]
        assert list(d.removed["source_id"]) == ["4"]
        assert round(float(d.price_drops.iloc[0]["change_pct"]), 1) == -10.0

    def test_first_snapshot_produces_no_events(self):
        cur = _frame([("s", "1", "SP", "A", 100.0)])
        d = diff_listings(pd.DataFrame(), cur)
        assert d.is_first_snapshot is True
        assert d.new.empty
        assert lifecycle_alerts(d) == []

    def test_small_noise_ignored_and_huge_changes_treated_as_suspect(self):
        prev = _frame([("s", "1", "SP", "A", 1000.0), ("s", "2", "SP", "A", 1000.0)])
        cur = _frame([("s", "1", "SP", "A", 990.0),    # −1%: ruído
                      ("s", "2", "SP", "A", 300.0)])   # −70%: suspeito
        d = diff_listings(prev, cur)
        assert d.price_drops.empty
        assert d.counts()["ignored_large_changes"] == 1
        assert d.unchanged == 1

    def test_duplicate_keys_do_not_inflate_events(self):
        prev = _frame([("s", "1", "SP", "A", 100.0)])
        cur = _frame([("s", "1", "SP", "A", 100.0), ("s", "1", "SP", "A", 100.0)])
        assert diff_listings(prev, cur).counts()["new"] == 0


class TestAlertsFromEvents:
    def test_one_alert_per_event_type_and_city(self):
        prev = _frame([("s", str(i), "SP", "A", 100.0) for i in range(5)]
                      + [("s", "r", "RJ", "B", 100.0)])
        cur = _frame([("s", "0", "SP", "A", 90.0), ("s", "1", "SP", "A", 92.0),
                      ("s", "n1", "SP", "A", 100.0), ("s", "n2", "SP", "A", 100.0)]
                     + [("s", "2", "SP", "A", 100.0), ("s", "3", "SP", "A", 100.0),
                        ("s", "4", "SP", "A", 100.0)])
        alerts = lifecycle_alerts(diff_listings(prev, cur))
        by_cat = {(a["category"], a["city"]): a for a in alerts}
        assert ("listing_price_drop", "SP") in by_cat
        assert ("new_listings", "SP") in by_cat
        assert ("removed_listings", "RJ") in by_cat
        assert by_cat[("listing_price_drop", "SP")]["value"] == 2.0
        assert len(alerts) == 3  # sem inundar o painel com um alerta por imóvel


class TestLiveDemoMarket:
    def _store(self, df):
        return df[DB_COLS].copy()

    def test_no_real_change_yields_no_events_through_cleaning(self):
        cleaner = DataCleaner()
        stored = self._store(cleaner.clean_listings(generate_synthetic_listings("sao-paulo", 300, seed=5)))
        same = evolve_synthetic_listings(stored, "sao-paulo", 300, seed=1, sold_rate=0, cut_rate=0)
        d = diff_listings(stored, cleaner.clean_listings(same))
        assert d.counts()["new"] == d.counts()["removed"] == 0
        assert d.counts()["price_drops"] == d.counts()["price_increases"] == 0

    def test_detects_injected_events_with_few_false_positives(self):
        cleaner = DataCleaner()
        stored = self._store(cleaner.clean_listings(generate_synthetic_listings("sao-paulo", 300, seed=5)))
        raw = evolve_synthetic_listings(stored, "sao-paulo", 300, seed=2)
        d = diff_listings(stored, cleaner.clean_listings(raw))
        true_new = set(raw.source_id) - set(stored.source_id)
        true_removed = set(stored.source_id) - set(raw.source_id)
        assert set(d.new["source_id"]) == true_new
        assert set(d.removed["source_id"]) == true_removed
        merged = stored.merge(raw[["source_id", "price"]], on="source_id", suffixes=("_p", "_c"))
        true_cut = set(merged.loc[merged.price_c < merged.price_p * 0.97, "source_id"])
        found = set(d.price_drops["key"].str.split("|").str[1])
        assert len(found & true_cut) >= 0.85 * len(true_cut)
        assert len(found - true_cut) <= 0.15 * max(1, len(true_cut))

    def test_ids_never_collide_across_many_rounds(self):
        cleaner = DataCleaner()
        cur = self._store(cleaner.clean_listings(generate_synthetic_listings("sao-paulo", 200, seed=3)))
        ever = set(cur.source_id)
        for r in range(5):
            raw = evolve_synthetic_listings(cur, "sao-paulo", 200, seed=r)
            assert raw.source_id.is_unique
            assert not ((set(raw.source_id) - set(cur.source_id)) & ever)
            ever |= set(raw.source_id)
            cur = self._store(cleaner.clean_listings(raw))

    def test_empty_previous_falls_back_to_fresh_generation(self):
        df = evolve_synthetic_listings(pd.DataFrame(), "curitiba", n_listings=20, seed=1)
        assert len(df) == 20

    def test_smaller_batch_requested_trims_market(self):
        cleaner = DataCleaner()
        stored = self._store(cleaner.clean_listings(generate_synthetic_listings("sao-paulo", 100, seed=4)))
        assert len(evolve_synthetic_listings(stored, "sao-paulo", n_listings=40, seed=1)) == 40


class TestSerialization:
    def test_nan_and_numpy_types_become_json_safe(self):
        df = pd.DataFrame({"a": [1.5, float("nan")], "b": [1, 2], "c": [True, False]})
        recs = df_to_records(df)
        assert recs[1]["a"] is None
        assert type(recs[0]["b"]) is int and type(recs[0]["c"]) is bool
        import json
        json.dumps(recs)  # não deve levantar
