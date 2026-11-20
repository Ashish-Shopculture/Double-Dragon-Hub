"""Parsing + calculation logic (no web code in here)."""
import io, re
import numpy as np
import pandas as pd

MK = ["DE", "ES", "FR", "IT"]


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce").fillna(0)


def read_report(raw: bytes):
    """Inventory or Sales CSV. Marketplace is read from the header line."""
    text = raw.decode("utf-8-sig", errors="replace")
    meta, _, body = text.partition("\n")
    m = re.search(r"Countries=\[([A-Z]{2})\]", meta)
    rg = re.search(r"Viewing Range=\[([^\]]+)\]", meta)
    mk = m.group(1) if m else None
    df = pd.read_csv(io.StringIO(body), dtype=str).fillna("")
    title = df["Product title"] if "Product title" in df else ""
    if "Sellable On Hand Units" in df:
        df = df.assign(_u=_num(df["Sellable On Hand Units"]), _t=title)
        g = df.groupby("ASIN").agg(u=("_u", "sum"), t=("_t", "first"))
        return "inv", mk, rg.group(1) if rg else "", {a: [float(r.u), r.t] for a, r in g.iterrows()}
    if "Ordered units" in df:
        df = df.assign(_u=_num(df["Ordered units"]), _r=_num(df["Ordered revenue"]), _t=title)
        g = df.groupby("ASIN").agg(u=("_u", "sum"), r=("_r", "sum"), t=("_t", "first"))
        return "sales", mk, rg.group(1) if rg else "", {a: [float(r.u), float(r.r), r.t] for a, r in g.iterrows()}
    return None, mk, "", {}


def read_po(raw: bytes):
    xl = pd.read_excel(io.BytesIO(raw), sheet_name=None, dtype=str)
    frames = [d for d in xl.values() if {"PO", "ASIN"} <= set(d.columns)]
    if not frames:
        return pd.DataFrame()
    d = pd.concat(frames).fillna("")
    dt = pd.to_datetime(d["Order date"], format="%m/%d/%Y", errors="coerce")
    dt = dt.fillna(pd.to_datetime(d["Order date"], errors="coerce"))
    out = pd.DataFrame({
        "po": d["PO"].str.strip(), "asin": d["ASIN"].str.strip(), "order_date": dt,
        "status": d.get("Status", ""), "requested": _num(d.get("Requested quantity", pd.Series("0", index=d.index))),
        "accepted": _num(d.get("Accepted quantity", pd.Series("0", index=d.index))),
        "title": d.get("Product name", ""),
    })
    out = out.dropna(subset=["order_date"])
    out = out[out.asin != ""]
    out["key"] = out.po + "|" + out.asin + "|" + out.order_date.dt.strftime("%Y-%m-%d") + "|" + out.requested.astype(int).astype(str)
    return out.drop_duplicates("key")


def read_availability(raw: bytes):
    xl = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None, dtype=str)
    res = {}
    for name, d in xl.items():
        if re.search(r"example|list|definition", name, re.I):
            continue
        d = d.fillna("")
        for i in range(min(len(d), 15)):
            row = list(d.iloc[i])
            if "ASIN" in row and "Current availability status" in row:
                ia, is_ = row.index("ASIN"), row.index("Current availability status")
                ip = row.index("Product name") if "Product name" in row else None
                for _, r in d.iloc[i + 1:].iterrows():
                    a = str(r.iloc[ia]).strip()
                    if a:
                        res[a] = [r.iloc[is_] or "Unknown", r.iloc[ip] if ip is not None else ""]
                break
    return res


def compute(po, inv, sales, av, low=21, redis=40, nopo=14, notes=None):
    today = pd.Timestamp.today().normalize()
    notes = notes or {}
    titles, asins = {}, set()
    if not po.empty:
        asins |= set(po.asin)
        titles.update({a: t for a, t in zip(po.asin, po.title) if isinstance(t, str) and t})
    for src, ti in ((inv, 1), (sales, 2), (av, 1)):
        for d in src.values():
            for a, e in d.items():
                asins.add(a)
                if e[ti]:
                    titles.setdefault(a, e[ti])
    if po.empty:
        last, c30, c90, call = {}, {}, {}, {}
    else:
        age = (today - po.order_date).dt.days
        last = po.groupby("asin").order_date.max().to_dict()
        c30 = po[age <= 30].groupby("asin").size().to_dict()
        c90 = po[age <= 90].groupby("asin").size().to_dict()
        call = po.groupby("asin").size().to_dict()
    rows = []
    for a in asins:
        rec = {"ASIN": a, "Title": titles.get(a, "")}
        per, rev = {}, 0.0
        for mk in MK:
            hasI = mk in inv
            u = inv[mk].get(a, [0])[0] if hasI else None
            s = sales.get(mk, {}).get(a, [0, 0])
            drr = s[0] / 7
            rev += s[1]
            if u is None:
                doc = np.nan
            elif drr > 0:
                doc = u / drr
            elif u > 0:
                doc = np.inf
            else:
                doc = np.nan
            stt = av[mk].get(a, ["Unknown"])[0] if mk in av else None
            per[mk] = dict(u=u, drr=drr, doc=doc, st=stt, hasI=hasI)
            rec.update({f"{mk} Units": u, f"{mk} DRR": round(drr, 2), f"{mk} DOC": doc,
                        f"{mk} Availability": stt or "n/a"})
        lm = last.get(a)
        days = int((today - lm).days) if lm is not None else None
        no_po = days is None or days > nopo
        lowM = [m for m in MK if per[m]["hasI"] and per[m]["drr"] > 0 and per[m]["doc"] < low]
        blocked = [m for m in lowM if per[m]["st"] and per[m]["st"] != "Available"]
        don = [m for m in MK if per[m]["hasI"] and per[m]["u"] > 0 and per[m]["doc"] >= redis]
        rec_m = [m for m in MK if per[m]["hasI"] and per[m]["u"] == 0 and m not in don]
        need = no_po and len(lowM) > 0
        redis_flag = bool(don and rec_m)
        act = []
        if need: act.append("NEED PO")
        elif no_po: act.append("No recent PO")
        if blocked: act.append("Availability blocked " + " ".join(blocked))
        if lowM: act.append("Low DOC " + " ".join(lowM))
        if redis_flag: act.append("Redistribute")
        n = notes.get(a, {})
        rec.update({
            "Weekly revenue": round(rev, 2), "Last PO": lm.date() if lm is not None else None,
            "Days since PO": days, "POs 30d": c30.get(a, 0), "POs 90d": c90.get(a, 0), "POs total": call.get(a, 0),
            "No recent PO": no_po, "Need PO": need, "Low DOC markets": ", ".join(lowM),
            "Blocked markets": ", ".join(blocked), "Surplus markets": ", ".join(don),
            "Zero-stock markets": ", ".join(rec_m), "Redistribution gap": redis_flag,
            "Action": " | ".join(act) or "OK",
            "Team status": n.get("status") or "", "Team note": n.get("note") or "",
        })
        rows.append(rec)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("Weekly revenue", ascending=False, kind="stable").reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)
    return df
