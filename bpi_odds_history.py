"""Historique SQLite des snapshots de marchés BPI, horodatés et comparables."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class OddsHistory:
    def __init__(self, database_path="data/bpi_odds_history.sqlite3"):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS odds_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    market_key TEXT NOT NULL,
                    period TEXT NOT NULL,
                    line TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_odds_history_lookup
                ON odds_snapshots(fixture_id, market_key, period, line, captured_at)
            """)

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def record(self, fixture_id, analysis):
        """Persiste chaque marché normalisé et renvoie le nombre de lignes."""
        captured_at = analysis.get("captured_at") or datetime.now(timezone.utc).isoformat()
        rows = []
        with self._connect() as db:
            for market in analysis.get("markets", []):
                key = str(market.get("key") or "unknown")
                period = str(market.get("period") if market.get("period") is not None else "")
                line = str(market.get("line") if market.get("line") is not None else "")
                db.execute(
                    """INSERT INTO odds_snapshots
                    (fixture_id, captured_at, market_key, period, line, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(fixture_id), captured_at, key, period, line,
                     json.dumps(market, ensure_ascii=False, sort_keys=True)),
                )
                rows.append((key, period, line))
        return len(rows)

    def history(self, fixture_id, market_key, period=None, line=None, limit=20):
        """Retourne les derniers snapshots du même fixture, marché, période et ligne."""
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            records = db.execute(
                """SELECT captured_at, payload_json FROM odds_snapshots
                WHERE fixture_id=? AND market_key=? AND period=? AND line=?
                ORDER BY captured_at DESC, id DESC LIMIT ?""",
                (str(fixture_id), str(market_key),
                 str(period) if period is not None else "",
                 str(line) if line is not None else "", limit),
            ).fetchall()
        return [{"captured_at": row[0], "market": json.loads(row[1])} for row in reversed(records)]

    def movement(self, fixture_id, market_key, period=None, line=None):
        """Compare le dernier prix aux prix précédents; aucun signal causal."""
        items = self.history(fixture_id, market_key, period, line, limit=2)
        if len(items) < 2:
            return {"status": "INSUFFICIENT_HISTORY", "snapshots": len(items), "changes": []}
        previous = {o["name"]: o for o in items[-2]["market"].get("outcomes", [])}
        current = {o["name"]: o for o in items[-1]["market"].get("outcomes", [])}
        changes = []
        for name in sorted(set(previous) & set(current)):
            old, new = previous[name].get("decimal"), current[name].get("decimal")
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                changes.append({"outcome": name, "previous_decimal": old,
                                "current_decimal": new, "delta": new - old})
        return {"status": "OBSERVED_MOVEMENT" if changes else "NO_COMPARABLE_CHANGE",
                "snapshots": len(items), "changes": changes,
                "note": "Variation descriptive, sans preuve de cause ni de flux d'argent."}
