"""Tiny Supabase helper (shared storage for the whole team)."""
import requests
import streamlit as st

BASE = st.secrets["SUPABASE_URL"].rstrip("/") + "/rest/v1"
KEY = st.secrets["SUPABASE_KEY"]
HEAD = {"apikey": KEY, "Content-Type": "application/json"}
if KEY.startswith("eyJ"):  # classic service_role key; new sb_secret_ keys only need the apikey header
    HEAD["Authorization"] = f"Bearer {KEY}"


def fetch(table, order):
    out, off = [], 0
    while True:
        r = requests.get(f"{BASE}/{table}", headers=HEAD, timeout=60,
                         params={"select": "*", "order": order, "offset": off, "limit": 1000})
        r.raise_for_status()
        rows = r.json()
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


def upsert(table, rows, conflict, ignore=False):
    pref = "resolution=ignore-duplicates" if ignore else "resolution=merge-duplicates"
    for i in range(0, len(rows), 500):
        r = requests.post(f"{BASE}/{table}", headers={**HEAD, "Prefer": pref}, timeout=60,
                          params={"on_conflict": conflict}, json=rows[i:i + 500])
        r.raise_for_status()


def insert(table, row):
    requests.post(f"{BASE}/{table}", headers=HEAD, json=row, timeout=30).raise_for_status()


def clear(table, col):
    requests.delete(f"{BASE}/{table}", headers=HEAD, params={col: "not.is.null"}, timeout=60).raise_for_status()
