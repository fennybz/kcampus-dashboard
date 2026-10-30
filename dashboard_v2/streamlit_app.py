"""Kalachandji's campus sales dashboard, hosted on Streamlit.

The dashboard itself is dashboard.html (charts, prep plan, insights, chat). This app
serves it full screen, connects it to Supabase and controls who sees what:

  * Visitors (no login) see Overview, Sales trends and Menu (items only). Before the page
    is sent, the server removes add-on names and choices, discounts and money detail, and
    merges any uploaded weeks in, so that data never reaches a visitor's browser.
  * Admins log in with ADMIN_PASSWORD and see everything, including add-ons, Prep plan,
    Insights, Money, Data & uploads and Ask AI. Only admins can add weekly files.

Secrets (Streamlit Cloud > app > Settings > Secrets):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "sb_publishable_..."   # anon / publishable key, never the service_role key
    ADMIN_PASSWORD = "a long passphrase"

Run supabase_setup.sql once in Supabase before the first deploy.
This file does not touch the original app.py or its tables.
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Kalachandji's Campus Sales", page_icon="🍛", layout="wide", initial_sidebar_state="collapsed")

HERE = Path(__file__).parent
SESSION_HOURS = 12
MARKER = '<script type="application/json" id="kc-data">'
# Column order the dashboard uses for uploaded weeks (kc-site.js COLS)
UPLOAD_COLS = ["date", "outlet", "channel", "category", "product", "row_type", "mod_group", "mod_choice", "mod_class", "qty", "units", "unit_price", "gross", "discount", "net"]


# ---------------------------------------------------------------- secrets
def secret(*names):
    """First secret found under any of the given names (top level or in a [supabase] section)."""
    try:
        sec = st.secrets
    except Exception:
        return ""
    for n in names:
        try:
            if n in sec and isinstance(sec[n], str) and sec[n].strip():
                return sec[n].strip()
        except Exception:
            pass
        try:
            sub = sec.get("supabase", {})
            short = n.lower().replace("supabase_", "")
            if short in sub and str(sub[short]).strip():
                return str(sub[short]).strip()
        except Exception:
            pass
    return ""


def key_role(key):
    """'anon', 'service_role', 'publishable', 'secret' or '' for a Supabase API key."""
    if key.startswith("sb_publishable_"):
        return "publishable"
    if key.startswith("sb_secret_"):
        return "secret"
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role", "")
    except Exception:
        return ""


def sb_get(url, key, path):
    req = urllib.request.Request(url.rstrip("/") + path, headers={"apikey": key, "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


@st.cache_data(ttl=300, show_spinner=False)
def table_ready(url, key):
    """True if supabase_setup.sql has been run (the dashboard table answers), else an error text."""
    try:
        sb_get(url, key, "/rest/v1/kc_dashboard_weeks?select=id&limit=1")
        return True
    except urllib.error.HTTPError as e:
        return "Supabase answered %s. Run supabase_setup.sql in the SQL Editor (it creates the kc_dashboard_weeks table)." % e.code
    except Exception as e:  # network, DNS
        return "Couldn't reach Supabase (%s). Check SUPABASE_URL." % type(e).__name__


# ---------------------------------------------------------------- admin login
ADMIN_PASSWORD = secret("ADMIN_PASSWORD")


def _sign(exp):
    k = ("kc-admin|" + ADMIN_PASSWORD).encode()
    return hmac.new(k, str(exp).encode(), hashlib.sha256).hexdigest()[:32]


def make_token():
    exp = int(time.time()) + SESSION_HOURS * 3600
    return "%d.%s" % (exp, _sign(exp))


def token_ok(tok):
    if not ADMIN_PASSWORD or not tok or "." not in tok:
        return False
    exp, sig = tok.split(".", 1)
    try:
        exp = int(exp)
    except ValueError:
        return False
    return exp > time.time() and hmac.compare_digest(sig, _sign(exp))


if "admin" not in st.session_state:
    st.session_state.admin = token_ok(st.query_params.get("s", ""))
is_admin = bool(st.session_state.admin) and bool(ADMIN_PASSWORD)


# ---------------------------------------------------------------- data for visitors
@st.cache_data(show_spinner=False)
def page_html():
    return (HERE / "dashboard.html").read_text(encoding="utf-8")


def split_page(html):
    i = html.index(MARKER) + len(MARKER)
    j = html.index("</script>", i)
    return html[:i], json.loads(html[i:j]), html[j:]


def decode(d):
    cols, strc, dic = d["cols"], set(d["strCols"]), d["dict"]
    out = []
    for r in d["rows"]:
        o = {}
        for c, v in zip(cols, r):
            o[c] = (None if v is None or v < 0 else dic[c][v]) if c in strc else v
        out.append(o)
    return out


def encode(rows, like):
    cols, strc = like["cols"], like["strCols"]
    dic = {c: [] for c in strc}
    idx = {c: {} for c in strc}
    enc = []
    for o in rows:
        r = []
        for c in cols:
            v = o.get(c)
            if c in idx:
                if v is None or v == "":
                    r.append(-1)
                else:
                    if v not in idx[c]:
                        idx[c][v] = len(dic[c])
                        dic[c].append(v)
                    r.append(idx[c][v])
            else:
                r.append(v)
        enc.append(r)
    return {**like, "dict": dic, "rows": enc}


def merge_uploads(rows, uploads):
    """Same rule as the dashboard: an uploaded week replaces the days it covers."""
    for u in sorted(uploads, key=lambda u: u.get("uploaded_at") or ""):
        new = []
        for a in u.get("packed") or []:
            o = dict(zip(UPLOAD_COLS, a))
            o["src"] = "upload"
            new.append(o)
        days = {o["date"] for o in new}
        rows = [r for r in rows if r["date"] not in days] + new
    return sorted(rows, key=lambda r: r["date"])


def strip_for_viewer(rows):
    """Keep sales by item; drop add-on names and choices, discounts and gross detail.

    Option revenue (size upgrades, premium curries, add-ons) is folded into one unnamed
    line per item and day, so revenue totals match the admin view exactly.
    """
    out, opts = [], OrderedDict()
    for r in rows:
        if r.get("row_type") == "Modifier":
            k = (r["date"], r["outlet"], r.get("channel"), r.get("category"), r["product"])
            opts[k] = opts.get(k, 0.0) + float(r.get("net") or 0)
        else:
            net = float(r.get("net") or 0)
            out.append({**r, "gross": net, "discount": 0.0, "src": "raw"})
    for (date, outlet, channel, category, product), net in opts.items():
        if abs(net) < 0.005:
            continue
        out.append({"date": date, "outlet": outlet, "channel": channel, "category": category, "product": product,
                    "row_type": "Modifier", "mod_group": "Options", "mod_choice": None, "mod_class": "Option",
                    "src": "raw", "qty": 0, "units": 0, "unit_price": 0, "gross": round(net, 2), "discount": 0.0, "net": round(net, 2)})
    return sorted(out, key=lambda r: r["date"])


@st.cache_data(ttl=300, show_spinner=False)
def viewer_html(url, key):
    head, data, tail = split_page(page_html())
    rows = decode(data)
    note = ""
    if url and key:
        try:
            ups = sb_get(url, key, "/rest/v1/kc_dashboard_weeks?select=id,uploaded_at,packed&order=uploaded_at.asc")
            rows = merge_uploads(rows, ups)
        except Exception as e:
            note = "Couldn't load the latest weeks (%s)." % type(e).__name__
    data = encode(strip_for_viewer(rows), data)
    data["asOf"] = max((r["date"] for r in rows), default=data.get("asOf", ""))
    body = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = head.replace(MARKER, '<script>window.KC_ROLE = "viewer";</script>\n' + MARKER) + body + tail
    return html, note


# ---------------------------------------------------------------- page
url = secret("SUPABASE_URL")
key = secret("SUPABASE_ANON_KEY", "SUPABASE_KEY")
role = key_role(key) if key else ""
notes = []
cfg = None
if not url or not key:
    notes.append(("info", "Supabase isn't connected yet. Add SUPABASE_URL and SUPABASE_ANON_KEY in this app's Secrets."))
elif role in ("service_role", "secret"):
    # This key would be visible to admins' browsers, so refuse to use it.
    notes.append(("error", "The Supabase key in Secrets is a service_role / secret key. Replace it with the anon (publishable) key from Supabase > Project Settings > API."))
    url = key = ""
else:
    ok = table_ready(url, key)
    if ok is True:
        cfg = {"url": url.rstrip("/"), "anonKey": key}
    else:
        notes.append(("warning", ok))
        url = key = ""
notes = notes if is_admin else []  # visitors don't need setup messages

st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stToolbar"], footer, #MainMenu { display: none !important; }
      .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
      [data-testid="stAppViewContainer"] > .main, [data-testid="stMain"] { padding: 0 !important; }
      div[data-testid="stVerticalBlock"] { gap: 0 !important; }
      iframe { display: block; border: 0; width: 100%; height: calc(100vh - NOTESpx) !important; }
      .st-key-kc_admin { position: fixed; left: 26px; bottom: 26px; z-index: 1000; width: auto !important; }
      .st-key-kc_admin button { border-radius: 10px; font-size: .82rem; padding: 4px 12px; min-height: 0; }
      @media (max-width: 900px) { .st-key-kc_admin { left: 12px; bottom: 12px; } }
    </style>
    """.replace("NOTES", str(64 * len(notes))),
    unsafe_allow_html=True,
)
for kind, text in notes:
    getattr(st, kind)(text)

# Admin login / logout button, pinned bottom-left over the dashboard's sidebar
with st.container(key="kc_admin"):
    if is_admin:
        if st.button("🔓 Admin · Log out", key="logout"):
            st.session_state.admin = False
            st.query_params.clear()
            st.rerun()
    else:
        with st.popover("🔒 Admin login"):
            if not ADMIN_PASSWORD:
                st.caption("Admin login is off. Add ADMIN_PASSWORD to this app's Secrets to turn it on.")
            else:
                with st.form("login", clear_on_submit=True, border=False):
                    pw = st.text_input("Admin password", type="password")
                    go = st.form_submit_button("Log in", type="primary")
                if go:
                    if hmac.compare_digest(pw.encode(), ADMIN_PASSWORD.encode()):
                        st.session_state.admin = True
                        st.query_params["s"] = make_token()
                        st.rerun()
                    else:
                        time.sleep(1.5)  # slow down guessing
                        st.error("Wrong password.")

if is_admin:
    html = page_html()
    inject = '<script>window.KC_ROLE = "admin";</script>\n'
    if cfg:
        inject += "<script>window.KC_SUPABASE = %s;</script>\n" % json.dumps(cfg)
    html = html.replace(MARKER, inject + MARKER, 1)
else:
    html, _note = viewer_html(url, key)
components.html(html, height=900, scrolling=True)
