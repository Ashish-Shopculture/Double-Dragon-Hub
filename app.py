import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Double Dragon EU PO & Inventory Hub", page_icon="🐉", layout="wide")
import db, logic
from logic import MK

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
#MainMenu,footer,.stDeployButton{visibility:hidden}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.4rem;max-width:1400px}
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.6)}70%{box-shadow:0 0 0 9px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
@keyframes grow{from{width:0}}
.brand{display:flex;align-items:center;gap:14px;margin-bottom:6px}
.mark{width:46px;height:46px;border-radius:13px;display:grid;place-items:center;color:#fff;font-weight:800;font-size:17px;background:linear-gradient(135deg,#5b5bf0,#a855f7);box-shadow:0 8px 24px rgba(91,91,240,.4)}
.brand h1{margin:0;font-size:26px;font-weight:800;letter-spacing:-.03em;line-height:1.1}
.brand p{margin:0;opacity:.6;font-size:13px}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;opacity:.8}
.live i{width:9px;height:9px;border-radius:50%;background:#22c55e;animation:pulse 2s infinite}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:14px 0}
.kpi,.mcard{position:relative;overflow:hidden;border:1px solid rgba(127,127,127,.22);background:rgba(127,127,127,.07);border-radius:16px;padding:16px 18px;animation:up .5s both;transition:.2s}
.kpi:hover,.mcard:hover{transform:translateY(-3px);border-color:rgba(91,91,240,.55);box-shadow:0 10px 28px rgba(91,91,240,.15)}
.kpi:before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:#5b5bf0}
.kpi.r:before{background:#ef4444}.kpi.a:before{background:#f59e0b}.kpi.g:before{background:#22c55e}
.kl{font-size:11px;text-transform:uppercase;letter-spacing:.07em;opacity:.65;font-weight:600}
.kn{font-size:34px;font-weight:800;letter-spacing:-.04em;margin-top:2px}
.kpi.r .kn{color:#ef4444}.kpi.a .kn{color:#f59e0b}.kpi.g .kn{color:#22c55e}
.ks{font-size:12px;opacity:.6}
.mcard h4{margin:0 0 10px;font-size:16px;font-weight:700}
.mrow{display:grid;grid-template-columns:1fr 1fr;gap:10px}.mrow b{font-size:20px;display:block;letter-spacing:-.02em}.mrow span{font-size:11px;opacity:.6}
.bar{display:flex;height:8px;border-radius:9px;overflow:hidden;background:rgba(127,127,127,.2);margin:12px 0 6px}
.bar i{animation:grow 1s both}
.sec{font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.6;font-weight:700;margin:26px 0 8px}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:8px 16px}
.stButton>button,.stDownloadButton>button{border-radius:10px;font-weight:600}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------- login ----------------
if "user" not in st.session_state:
    st.markdown('<div class="brand"><div class="mark">DD</div><div><h1>Double Dragon</h1><p>EU PO &amp; Inventory Hub</p></div></div>', unsafe_allow_html=True)
    with st.form("login"):
        name = st.text_input("Your name")
        pw = st.text_input("Team password", type="password")
        if st.form_submit_button("Enter hub", type="primary"):
            if pw == st.secrets["APP_PASSWORD"] and name.strip():
                st.session_state.user = name.strip()
                st.rerun()
            else:
                st.error("Wrong password or missing name.")
    st.stop()
USER = st.session_state.user


# ---------------- shared data ----------------
@st.cache_data(ttl=60, show_spinner="Loading shared data…")
def load_all():
    po = pd.DataFrame(db.fetch("po_lines", "key"))
    if not po.empty:
        po["order_date"] = pd.to_datetime(po["order_date"])
        po = po.rename(columns={"requested": "requested", "accepted": "accepted"})
    inv, sales, av, meta = {}, {}, {}, []
    for r in db.fetch("reports", "id"):
        {"inv": inv, "sales": sales, "av": av}[r["kind"]][r["mk"]] = r["data"]
        meta.append(r)
    notes = {n["asin"]: n for n in db.fetch("notes", "asin")}
    log = db.fetch("app_log", "id.desc")[:12]
    return po, inv, sales, av, meta, notes, log


def refresh():
    st.cache_data.clear()
    st.rerun()


def log(msg):
    db.insert("app_log", {"user_name": USER, "msg": msg})


po, inv, sales, av, meta, notes, logs = load_all()

# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown(f"**👤 {USER}**")
    low = st.number_input("Low DOC alert (days)", 1, 120, 21)
    redis = st.number_input("Redistribution surplus (days)", 5, 365, 40)
    nopo = st.number_input("No-PO flag after (days)", 1, 120, 14)
    if st.button("🔄 Refresh data", width="stretch"):
        refresh()
    if st.button("Log out", width="stretch"):
        del st.session_state["user"]
        st.rerun()
    st.caption("DRR = weekly ordered units ÷ 7 · DOC = sellable on-hand ÷ DRR · Any PO line counts as a PO received.")

df = logic.compute(po, inv, sales, av, low, redis, nopo, notes)

st.markdown('<div class="brand"><div class="mark">DD</div><div><h1>Double Dragon</h1><p>EU PO &amp; Inventory Hub · DE · ES · FR · IT</p></div><div class="live"><i></i>Shared · live</div></div>', unsafe_allow_html=True)
t_dash, t_trk, t_red, t_po, t_up = st.tabs(["📊 Dashboard", "🔎 ASIN tracker", "🔀 Redistribution", "🧾 PO history", "⬆️ Upload & data"])


def kpi(label, val, sub, tone="", i=0):
    return f'<div class="kpi {tone}" style="animation-delay:{i*70}ms"><div class="kl">{label}</div><div class="kn">{int(val):,}</div><div class="ks">{sub}</div></div>'


def to_excel(d):
    b = io.BytesIO()
    base = ["Rank", "ASIN", "Title", "Weekly revenue", "Last PO", "Days since PO"]
    mk_cols = [c for c in d.columns if c[:2] in MK and c[2] == " "]
    def put(w, name, x):
        (x if len(x) else pd.DataFrame({"Note": ["None"]})).replace([np.inf], "No sales").to_excel(w, sheet_name=name, index=False)
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        summ = pd.DataFrame({"Metric": ["ASINs tracked", f"Getting PO (last {nopo}d)", "No recent PO", "Need PO (low DOC + no PO)", "Availability blocked", "Redistribution gaps", "Generated"],
                             "Value": [len(d), int((~d["No recent PO"]).sum()), int(d["No recent PO"].sum()), int(d["Need PO"].sum()),
                                       int((d["Blocked markets"] != "").sum()), int(d["Redistribution gap"].sum()), str(pd.Timestamp.today().date())]})
        put(w, "Summary", summ)
        put(w, "Need PO", d[d["Need PO"]][base + ["Low DOC markets"] + mk_cols])
        put(w, "Availability blocked", d[d["Blocked markets"] != ""][base + ["Blocked markets"] + mk_cols])
        put(w, "Redistribution", d[d["Redistribution gap"]][base + ["Surplus markets", "Zero-stock markets"] + mk_cols])
        put(w, "Full tracker", d[base + ["POs 30d", "POs 90d", "POs total", "Action", "Team status", "Team note"] + mk_cols])
    return b.getvalue()


# ---------------- dashboard ----------------
with t_dash:
    if df.empty:
        st.info("No data yet. Open the **Upload & data** tab and upload your reports.")
    else:
        k = [("ASINs tracked", len(df), "across 4 marketplaces", ""),
             ("Getting PO", (~df["No recent PO"]).sum(), f"PO in last {nopo} days", "g"),
             ("No recent PO", df["No recent PO"].sum(), f"none in {nopo}+ days", "a"),
             ("Need PO", df["Need PO"].sum(), f"low DOC &lt; {low}d and no PO", "r"),
             ("Availability blocked", (df["Blocked markets"] != "").sum(), "low DOC but not Available", "r"),
             ("Redistribution gaps", df["Redistribution gap"].sum(), f"≥{redis}d in one market, 0 in another", "r")]
        st.markdown('<div class="grid">' + "".join(kpi(*x, i=i) for i, x in enumerate(k)) + "</div>", unsafe_allow_html=True)
        st.download_button("⬇️ Download report for Amazon (Excel)", to_excel(df), f"DoubleDragon_EU_PO_Report_{pd.Timestamp.today().date()}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        st.markdown('<div class="sec">Marketplaces</div>', unsafe_allow_html=True)
        cards = ""
        for i, m in enumerate(MK):
            has = m in inv
            units = df[f"{m} Units"].fillna(0).sum()
            rev = sum(sales.get(m, {}).get(a, [0, 0])[1] for a in df["ASIN"])
            lw = df["Low DOC markets"].str.contains(m).sum()
            oos = ((df[f"{m} Units"] == 0) & (df[f"{m} DRR"] > 0)).sum()
            vc = df[f"{m} Availability"].value_counts()
            a_, t_, p_ = vc.get("Available", 0), vc.get("Temporarily unavailable", 0), vc.get("Permanently unavailable", 0)
            tot = max(a_ + t_ + p_, 1)
            txt = f"{a_} available · {t_} temp. · {p_} perm. unavailable" if m in av else "availability file not loaded"
            cards += (f'<div class="mcard" style="animation-delay:{i*90}ms"><h4>{m} {"" if has else "· no inventory file"}</h4><div class="mrow">'
                      f'<div><b>{units:,.0f}</b><span>Sellable units</span></div><div><b>€{rev:,.0f}</b><span>Weekly revenue</span></div>'
                      f'<div><b style="color:#ef4444">{lw}</b><span>Low DOC ASINs</span></div><div><b style="color:#f59e0b">{oos}</b><span>Out of stock, still selling</span></div></div>'
                      f'<div class="bar"><i style="width:{a_/tot*100}%;background:#22c55e"></i><i style="width:{t_/tot*100}%;background:#f59e0b"></i><i style="width:{p_/tot*100}%;background:#ef4444"></i></div>'
                      f'<span style="font-size:12px;opacity:.6">{txt}</span></div>')
        st.markdown(f'<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">{cards}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sec">Stock health by marketplace (ASIN count)</div>', unsafe_allow_html=True)
        buckets = {"Out of stock, selling": "#ef4444", f"Low DOC (<{low}d)": "#f59e0b", "Healthy": "#22c55e", f"Surplus (≥{redis}d)": "#5b5bf0"}
        vals = {b: [] for b in buckets}
        for m in MK:
            u, drr, doc = df[f"{m} Units"], df[f"{m} DRR"], df[f"{m} DOC"]
            vals["Out of stock, selling"].append(int(((u == 0) & (drr > 0)).sum()))
            vals[f"Low DOC (<{low}d)"].append(int(((u > 0) & (doc < low)).sum()))
            vals["Healthy"].append(int(((doc >= low) & (doc < redis)).sum()))
            vals[f"Surplus (≥{redis}d)"].append(int((doc >= redis).sum()))
        fig = go.Figure([go.Bar(name=b, x=MK, y=vals[b], marker_color=c) for b, c in buckets.items()])
        fig.update_layout(barmode="stack", height=320, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")

        st.markdown('<div class="sec">Top escalations by revenue</div>', unsafe_allow_html=True)
        top = df[df["Need PO"] | (df["Blocked markets"] != "") | df["Redistribution gap"]].head(10)
        st.dataframe(top[["Rank", "ASIN", "Title", "Weekly revenue", "Days since PO", "Action"]], hide_index=True, width="stretch")

# ---------------- tracker ----------------
def docfmt(x):
    return "n/a" if pd.isna(x) else "No sales" if np.isinf(x) else f"{x:.0f}d"


def docstyle(x):
    if pd.isna(x) or np.isinf(x):
        return ""
    return "background-color:rgba(239,68,68,.25)" if x < low else "background-color:rgba(91,91,240,.22)" if x >= redis else "background-color:rgba(34,197,94,.18)"


with t_trk:
    if df.empty:
        st.info("Upload reports first.")
    else:
        c1, c2 = st.columns([3, 2])
        flt = c1.radio("Filter", ["All", "Need PO", "No recent PO", "Low DOC", "Availability blocked", "Redistribution", "Has team status"], horizontal=True, label_visibility="collapsed")
        q = c2.text_input("Search", placeholder="Search ASIN or title", label_visibility="collapsed")
        m = {"All": df["ASIN"].notna(), "Need PO": df["Need PO"], "No recent PO": df["No recent PO"], "Low DOC": df["Low DOC markets"] != "",
             "Availability blocked": df["Blocked markets"] != "", "Redistribution": df["Redistribution gap"], "Has team status": df["Team status"] != ""}[flt]
        if q:
            m &= (df["ASIN"] + " " + df["Title"]).str.contains(q, case=False, regex=False)
        view = df[m].reset_index(drop=True)
        cols = ["Rank", "ASIN", "Title", "Weekly revenue", "Last PO", "Days since PO", "Action", "Team status"] + [f"{x} {k}" for x in MK for k in ("Units", "DOC")] + [f"{x} Availability" for x in MK]
        doc_cols = [f"{x} DOC" for x in MK]
        sty = view[cols].style.format({c: docfmt for c in doc_cols}).format({"Weekly revenue": "€{:,.0f}"})
        sty = (sty.map if hasattr(sty, "map") else sty.applymap)(docstyle, subset=doc_cols)
        st.caption(f"{len(view)} of {len(df)} ASINs · ranked by weekly revenue · click a row to open the ASIN and add team notes")
        ev = st.dataframe(sty, hide_index=True, width="stretch", height=480, on_select="rerun", selection_mode="single-row", key="trk")
        if ev.selection.rows:
            r = view.iloc[ev.selection.rows[0]]
            a = r["ASIN"]
            st.markdown(f"### {a}  ·  rank #{r['Rank']}")
            st.caption(r["Title"])
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Marketplace position**")
                st.dataframe(pd.DataFrame([{"Market": x, "Units": r[f"{x} Units"], "DRR/day": r[f"{x} DRR"], "DOC": docfmt(r[f"{x} DOC"]), "Availability": r[f"{x} Availability"]} for x in MK]), hide_index=True, width="stretch")
                st.markdown("**Recent PO lines**")
                pl = po[po.asin == a].sort_values("order_date", ascending=False).head(20) if not po.empty else pd.DataFrame()
                st.dataframe(pl[["order_date", "po", "status", "requested", "accepted"]] if len(pl) else pd.DataFrame({"": ["No PO received yet"]}), hide_index=True, width="stretch")
            with d2:
                st.markdown("**Team follow-up**")
                n = notes.get(a, {})
                opts = ["", "Open", "Escalated to Amazon", "Waiting on Amazon", "Resolved"]
                with st.form("note"):
                    s = st.selectbox("Status", opts, index=opts.index(n.get("status") or ""))
                    t = st.text_area("Notes / case IDs / owner", n.get("note") or "", height=140)
                    if st.form_submit_button("Save", type="primary"):
                        db.upsert("notes", [{"asin": a, "status": s, "note": t, "updated_by": USER, "updated_at": pd.Timestamp.utcnow().isoformat()}], "asin")
                        log(f"updated {a} → {s or 'no status'}")
                        refresh()
                if n.get("updated_by"):
                    st.caption(f"Last updated by {n['updated_by']}")

# ---------------- redistribution ----------------
with t_red:
    st.caption(f"ASINs where a marketplace holds ≥ {redis} days of cover (or stock with no sales) while another marketplace has zero stock. With WePay / Pan-EU, Amazon should rebalance these automatically.")
    rd = df[df["Redistribution gap"]] if not df.empty else df
    if rd.empty:
        st.success("No redistribution gaps found.")
    else:
        rows = []
        for _, r in rd.iterrows():
            rows.append({"Rank": r["Rank"], "ASIN": r["ASIN"], "Title": r["Title"], "Weekly revenue": r["Weekly revenue"],
                         "Surplus in": ", ".join(f"{x} ({r[f'{x} Units']:.0f}u, {docfmt(r[f'{x} DOC'])})" for x in r["Surplus markets"].split(", ")),
                         "Zero stock in": ", ".join(f"{x}" + (f" (selling {r[f'{x} DRR']}/day)" if r[f"{x} DRR"] > 0 else "") + ("" if r[f"{x} Availability"] in ("Available", "n/a") else f" [{r[f'{x} Availability']}]") for x in r["Zero-stock markets"].split(", "))})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------------- PO history ----------------
with t_po:
    if po.empty:
        st.info("No PO history yet. Upload the PO export in the Upload tab.")
    else:
        a, b, c = st.columns(3)
        a.metric("PO lines in history", f"{len(po):,}")
        b.metric("ASINs that ever got a PO", f"{po.asin.nunique():,}")
        c.metric("History range", f"{po.order_date.min().date()} → {po.order_date.max().date()}")
        h = df[["Rank", "ASIN", "Title", "Last PO", "Days since PO", "POs 30d", "POs 90d", "POs total"]].copy()
        h["_s"] = h["Days since PO"].fillna(10**6)
        st.dataframe(h.sort_values("_s", ascending=False).drop(columns="_s"), hide_index=True, width="stretch", height=520)

# ---------------- upload ----------------
with t_up:
    st.markdown("Upload your reports, then press **Save to shared hub**. Everyone on the team will see the new data.")
    with st.form("up", clear_on_submit=True):
        f_po = st.file_uploader("1 · PO export (.xls / .xlsx). Full year first, then weekly.", type=["xls", "xlsx"], accept_multiple_files=True)
        f_is = st.file_uploader("2 · Inventory & Sales CSVs. Select all at once; marketplace is detected automatically.", type=["csv"], accept_multiple_files=True)
        st.markdown("3 · Availability reports (one per marketplace)")
        cols = st.columns(4)
        f_av = {m: cols[i].file_uploader(m, type=["xlsx"], key=f"av{m}") for i, m in enumerate(MK)}
        go_ = st.form_submit_button("Save to shared hub", type="primary")
    if go_:
        try:
            with st.spinner("Saving…"):
                for f in f_po:
                    d = logic.read_po(f.getvalue())
                    if d.empty:
                        st.warning(f"{f.name}: no PO rows found")
                        continue
                    have = set(po["key"]) if not po.empty else set()
                    new = d[~d.key.isin(have)]
                    rows = new.assign(order_date=new.order_date.dt.strftime("%Y-%m-%d"))[["key", "po", "asin", "order_date", "status", "requested", "accepted", "title"]].to_dict("records")
                    db.upsert("po_lines", rows, "key", ignore=True)
                    log(f"added {len(rows)} PO lines from {f.name}")
                    st.success(f"{f.name}: {len(rows)} new PO lines added ({len(d) - len(rows)} already in history)")
                for f in f_is:
                    kind, mk, rg, data = logic.read_report(f.getvalue())
                    if kind is None or mk not in MK:
                        st.warning(f"{f.name}: not recognised (need an Inventory/Sales report for DE, ES, FR or IT)")
                        continue
                    db.upsert("reports", [{"id": f"{kind}_{mk}", "kind": kind, "mk": mk, "rng": rg, "filename": f.name, "uploaded_by": USER, "uploaded_at": pd.Timestamp.utcnow().isoformat(), "data": data}], "id")
                    log(f"uploaded {mk} {'inventory' if kind == 'inv' else 'sales'} ({len(data)} ASINs)")
                    st.success(f"{mk} {'inventory' if kind == 'inv' else 'sales'} saved")
                for mk, f in f_av.items():
                    if f:
                        data = logic.read_availability(f.getvalue())
                        if not data:
                            st.warning(f"{mk}: no availability rows found")
                            continue
                        db.upsert("reports", [{"id": f"av_{mk}", "kind": "av", "mk": mk, "rng": "", "filename": f.name, "uploaded_by": USER, "uploaded_at": pd.Timestamp.utcnow().isoformat(), "data": data}], "id")
                        log(f"uploaded {mk} availability ({len(data)} ASINs)")
                        st.success(f"{mk} availability saved")
            st.cache_data.clear()
            st.button("Show updated dashboard", on_click=lambda: None)
        except Exception as e:
            st.error(f"Could not save: {e}")

    st.markdown('<div class="sec">Data status</div>', unsafe_allow_html=True)
    mm = {(r["kind"], r["mk"]): r for r in meta}
    rows = []
    for m in MK:
        row = {"Market": m}
        for k, lbl in (("inv", "Inventory"), ("sales", "Sales"), ("av", "Availability")):
            r = mm.get((k, m))
            row[lbl] = f"✓ {r['rng'] or r['filename']} · {r['uploaded_by']} · {r['uploaded_at'][:16].replace('T', ' ')}" if r else "✗ missing"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown('<div class="sec">Recent team activity</div>', unsafe_allow_html=True)
    for l in logs:
        st.markdown(f"**{l['user_name']}** {l['msg']} <span style='opacity:.5'>· {l['at'][:16].replace('T', ' ')}</span>", unsafe_allow_html=True)
    with st.expander("Danger zone"):
        if st.checkbox("I understand this deletes PO history for everyone") and st.button("Clear all PO history"):
            db.clear("po_lines", "key")
            log("cleared PO history")
            refresh()
