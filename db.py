import os
import psycopg2
from psycopg2.extras import RealDictCursor

SCHEMA = """
CREATE TABLE IF NOT EXISTS personel (
    id SERIAL PRIMARY KEY,
    ad TEXT NOT NULL,
    soyad TEXT NOT NULL,
    unvan TEXT NOT NULL,
    olusturma TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS belge (
    id SERIAL PRIMARY KEY,
    personel_id INT NOT NULL REFERENCES personel(id) ON DELETE CASCADE,
    belge_adi TEXT NOT NULL,
    baslangic DATE,
    bitis DATE NOT NULL,
    dosya_adi TEXT,
    bildirim_15gun_gonderildi BOOLEAN NOT NULL DEFAULT FALSE,
    bildirim_bitti_gonderildi BOOLEAN NOT NULL DEFAULT FALSE,
    olusturma TIMESTAMPTZ DEFAULT now(),
    UNIQUE (personel_id, belge_adi, bitis)
);
"""


def _url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    import streamlit as st  # sadece uygulamada gerekir
    return st.secrets["DATABASE_URL"]


def _conn():
    return psycopg2.connect(_url(), cursor_factory=RealDictCursor)


def query(sql, params=None):
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql, params=None):
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def init_db():
    execute(SCHEMA)
