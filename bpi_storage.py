"""Stockage SQLite local des analyses BPI (prototype).

Attention : sur Streamlit Community Cloud, le disque local peut être réinitialisé
lors d'un redéploiement/redémarrage. Exporter régulièrement la base; une base
hébergée externe sera nécessaire pour une persistance garantie.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / "data" / "bpi_history.sqlite3"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at_utc TEXT NOT NULL,
                game_date TEXT,
                competition TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                halftime_home INTEGER NOT NULL,
                halftime_away INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                final_home INTEGER,
                final_away INTEGER,
                result_recorded_at_utc TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(game_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_competition ON predictions(competition)")


def save_prediction(payload):
    init_db()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO predictions (
                created_at_utc, game_date, competition, home_team, away_team,
                halftime_home, halftime_away, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            payload.get("date_match"), payload.get("competition"),
            payload["domicile"], payload["exterieur"],
            int(payload["score_pause_domicile"]), int(payload["score_pause_exterieur"]),
            json.dumps(payload, ensure_ascii=False)
        ))
        return cur.lastrowid


def list_predictions(limit=500):
    init_db()
    with _connect() as conn:
        rows = conn.execute("""
            SELECT id, created_at_utc, game_date, competition, home_team, away_team,
                   halftime_home, halftime_away, final_home, final_away, payload_json
            FROM predictions ORDER BY id DESC LIMIT ?
        """, (int(limit),)).fetchall()
    return [dict(row) for row in rows]


def record_final_score(prediction_id, final_home, final_away):
    init_db()
    with _connect() as conn:
        cur = conn.execute("""
            UPDATE predictions
            SET final_home=?, final_away=?, result_recorded_at_utc=?
            WHERE id=?
        """, (int(final_home), int(final_away), datetime.now(timezone.utc).isoformat(), int(prediction_id)))
        return cur.rowcount == 1


def export_database_bytes():
    init_db()
    return DB_PATH.read_bytes()
