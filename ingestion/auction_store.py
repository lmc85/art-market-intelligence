"""SQLite storage for normalized auction lots and ingest runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ingestion.auction_models import AuctionLot, lot_from_row
from ingestion.models import utc_now_iso


DEFAULT_DB_PATH = Path("data/auction/auction_pipeline.sqlite")


class AuctionStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.ensure_schema()

    def close(self) -> None:
        self.connection.close()

    def ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS auction_ingest_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT NOT NULL,
              source_name TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              sale_url TEXT,
              sale_query TEXT,
              limit_requested INTEGER,
              raw_snapshot_path TEXT,
              records_seen INTEGER DEFAULT 0,
              records_written INTEGER DEFAULT 0,
              error TEXT
            );

            CREATE TABLE IF NOT EXISTS auction_lots (
              identity_key TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              source_name TEXT NOT NULL,
              auction_house TEXT NOT NULL,
              sale_id TEXT,
              sale_title TEXT,
              sale_url TEXT,
              lot_id TEXT,
              source_record_id TEXT,
              title TEXT,
              artists_json TEXT,
              style TEXT,
              auction_date TEXT,
              currency TEXT,
              estimate_low REAL,
              estimate_high REAL,
              estimate_display TEXT,
              starting_price_amount REAL,
              starting_price_display TEXT,
              result_price_amount REAL,
              result_price_display TEXT,
              last_sold_price_amount REAL,
              last_sold_price_display TEXT,
              last_sold_date TEXT,
              source_url TEXT,
              image_url TEXT,
              medium TEXT,
              dimensions TEXT,
              description TEXT,
              record_source TEXT,
              notes TEXT,
              quality_flags_json TEXT,
              prediction_ready INTEGER NOT NULL DEFAULT 0,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              raw_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_auction_lots_source ON auction_lots(source_id);
            CREATE INDEX IF NOT EXISTS idx_auction_lots_sale ON auction_lots(source_id, sale_id);
            CREATE INDEX IF NOT EXISTS idx_auction_lots_date ON auction_lots(auction_date);
            CREATE INDEX IF NOT EXISTS idx_auction_lots_prediction_ready ON auction_lots(prediction_ready);
            """
        )
        self.connection.commit()

    def start_run(
        self,
        source_id: str,
        source_name: str,
        sale_url: str,
        sale_query: str,
        limit_requested: int,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO auction_ingest_runs (
              source_id, source_name, status, started_at, sale_url, sale_query, limit_requested
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_id, source_name, "running", utc_now_iso(), sale_url, sale_query, limit_requested),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        records_seen: int,
        records_written: int,
        raw_snapshot_path: str = "",
        error: str = "",
    ) -> None:
        self.connection.execute(
            """
            UPDATE auction_ingest_runs
            SET status = ?, finished_at = ?, records_seen = ?, records_written = ?,
                raw_snapshot_path = ?, error = ?
            WHERE id = ?
            """,
            (status, utc_now_iso(), records_seen, records_written, raw_snapshot_path, error, run_id),
        )
        self.connection.commit()

    def clear_source(self, source_id: str) -> None:
        self.connection.execute("DELETE FROM auction_lots WHERE source_id = ?", (source_id,))
        self.connection.commit()

    def upsert_lots(self, lots: Iterable[AuctionLot]) -> int:
        count = 0
        now = utc_now_iso()
        for lot in lots:
            values = lot.as_db_values()
            values["first_seen_at"] = now
            self.connection.execute(
                """
                INSERT INTO auction_lots (
                  identity_key, source_id, source_name, auction_house, sale_id, sale_title,
                  sale_url, lot_id, source_record_id, title, artists_json, style,
                  auction_date, currency, estimate_low, estimate_high, estimate_display,
                  starting_price_amount, starting_price_display, result_price_amount,
                  result_price_display, last_sold_price_amount, last_sold_price_display,
                  last_sold_date, source_url, image_url, medium, dimensions, description,
                  record_source, notes, quality_flags_json, prediction_ready,
                  first_seen_at, last_seen_at, raw_json
                )
                VALUES (
                  :identity_key, :source_id, :source_name, :auction_house, :sale_id, :sale_title,
                  :sale_url, :lot_id, :source_record_id, :title, :artists_json, :style,
                  :auction_date, :currency, :estimate_low, :estimate_high, :estimate_display,
                  :starting_price_amount, :starting_price_display, :result_price_amount,
                  :result_price_display, :last_sold_price_amount, :last_sold_price_display,
                  :last_sold_date, :source_url, :image_url, :medium, :dimensions, :description,
                  :record_source, :notes, :quality_flags_json, :prediction_ready,
                  :first_seen_at, :last_seen_at, :raw_json
                )
                ON CONFLICT(identity_key) DO UPDATE SET
                  source_name = excluded.source_name,
                  auction_house = excluded.auction_house,
                  sale_id = excluded.sale_id,
                  sale_title = excluded.sale_title,
                  sale_url = excluded.sale_url,
                  lot_id = excluded.lot_id,
                  source_record_id = excluded.source_record_id,
                  title = excluded.title,
                  artists_json = excluded.artists_json,
                  style = excluded.style,
                  auction_date = excluded.auction_date,
                  currency = excluded.currency,
                  estimate_low = excluded.estimate_low,
                  estimate_high = excluded.estimate_high,
                  estimate_display = excluded.estimate_display,
                  starting_price_amount = excluded.starting_price_amount,
                  starting_price_display = excluded.starting_price_display,
                  result_price_amount = excluded.result_price_amount,
                  result_price_display = excluded.result_price_display,
                  last_sold_price_amount = excluded.last_sold_price_amount,
                  last_sold_price_display = excluded.last_sold_price_display,
                  last_sold_date = excluded.last_sold_date,
                  source_url = excluded.source_url,
                  image_url = excluded.image_url,
                  medium = excluded.medium,
                  dimensions = excluded.dimensions,
                  description = excluded.description,
                  record_source = excluded.record_source,
                  notes = excluded.notes,
                  quality_flags_json = excluded.quality_flags_json,
                  prediction_ready = excluded.prediction_ready,
                  last_seen_at = excluded.last_seen_at,
                  raw_json = excluded.raw_json
                """,
                values,
            )
            count += 1
        self.connection.commit()
        return count

    def lots_for_feed(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT * FROM auction_lots
            ORDER BY auction_date DESC, last_seen_at DESC, identity_key ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [lot_from_row(dict(row)).to_feed_item() for row in rows]

    def latest_run(self) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT * FROM auction_ingest_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def quality_summary(self) -> Dict[str, Any]:
        total = self.connection.execute("SELECT COUNT(*) AS count FROM auction_lots").fetchone()["count"]
        prediction_ready = self.connection.execute(
            "SELECT COUNT(*) AS count FROM auction_lots WHERE prediction_ready = 1"
        ).fetchone()["count"]
        missing = {
            "missing_artist": 0,
            "missing_estimate": 0,
            "missing_result_price": 0,
            "missing_medium": 0,
            "missing_dimensions": 0,
            "missing_prior_sale": 0,
        }
        for row in self.connection.execute("SELECT quality_flags_json FROM auction_lots"):
            flags = json.loads(row["quality_flags_json"] or "{}")
            if not flags.get("has_artist"):
                missing["missing_artist"] += 1
            if not flags.get("has_estimate"):
                missing["missing_estimate"] += 1
            if not flags.get("has_result_price"):
                missing["missing_result_price"] += 1
            if not flags.get("has_medium"):
                missing["missing_medium"] += 1
            if not flags.get("has_dimensions"):
                missing["missing_dimensions"] += 1
            if not flags.get("has_prior_sale"):
                missing["missing_prior_sale"] += 1
        return {"total": total, "prediction_ready": prediction_ready, **missing}


def write_feed_json(items: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
