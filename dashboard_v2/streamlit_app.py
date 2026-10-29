"""Kalachandji's campus sales dashboard, hosted on Streamlit.

The dashboard itself is dashboard.html (charts, prep plan, insights, chat). This app
serves it full screen and connects it to Supabase so weekly uploads are shared:

  * Everyone with the link sees the same data.
  * "Add weekly file" saves the week to Supabase (table kc_dashboard_weeks) after a PIN check.
  * Run supabase_setup.sql once in Supabase before the first deploy.

Secrets (Streamlit Cloud > app > Settings > Secrets):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "eyJ..."   # the anon / publishable key, never the service_role key

This file does not touch the original app.py or its tables.
"""
import base64
import json
import urllib.request
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Kalachandji's Campus Sales", page_icon="🍛", layout="wide", initial_sidebar_state="collapsed")

HERE = Path(__file__).parent


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


@st.cache_data(ttl=300, show_spinner=False)
def table_ready(url, key):
    """True if supabase_setup.sql has been run (the dashboard table answers), else an error text."""
    req = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/kc_dashboard_weeks?select=id&limit=1",
        headers={"apikey": key, "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return "Supabase answered %s. Run supabase_setup.sql in the SQL Editor (it creates the kc_dashboard_weeks table)." % e.code
    except Exception as e:  # network, DNS
        return "Couldn't reach Supabase (%s). Check SUPABASE_URL." % type(e).__name__


@st.cache_data(show_spinner=False)
def page_html():
    return (HERE / "dashboard.html").read_text(encoding="utf-8")


url = secret("SUPABASE_URL")
key = secret("SUPABASE_ANON_KEY", "SUPABASE_KEY")
role = key_role(key) if key else ""
notes = []
cfg = None
if not url or not key:
    notes.append(("info", "Supabase isn't connected yet, so uploaded weeks stay in each person's browser. Add SUPABASE_URL and SUPABASE_ANON_KEY in this app's Secrets."))
elif role in ("service_role", "secret"):
    # This key would be visible to every visitor's browser, so refuse to use it.
    notes.append(("error", "The Supabase key in Secrets is a service_role / secret key. Don't use it here: replace it with the anon (publishable) key from Supabase > Project Settings > API."))
else:
    ok = table_ready(url, key)
    if ok is True:
        cfg = {"url": url.rstrip("/"), "anonKey": key}
    else:
        notes.append(("warning", ok))

# Full-screen layout: hide Streamlit's header and padding so the dashboard fills the window.
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], [data-testid="stToolbar"], footer, #MainMenu { display: none !important; }
      .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
      [data-testid="stAppViewContainer"] > .main, [data-testid="stMain"] { padding: 0 !important; }
      div[data-testid="stVerticalBlock"] { gap: 0 !important; }
      iframe { display: block; border: 0; width: 100%; height: calc(100vh - NOTESpx) !important; }
    </style>
    """.replace("NOTES", str(64 * len(notes))),
    unsafe_allow_html=True,
)
for kind, text in notes:
    getattr(st, kind)(text)

html = page_html()
marker = '<script type="application/json" id="kc-data">'
inject = "<script>window.KC_SUPABASE = %s;</script>\n" % json.dumps(cfg) if cfg else ""
if inject:
    html = html.replace(marker, inject + marker, 1)
components.html(html, height=900, scrolling=True)
