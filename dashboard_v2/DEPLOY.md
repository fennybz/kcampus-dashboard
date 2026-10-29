# Deploy the new dashboard on Streamlit (with Supabase)

This folder is a second Streamlit app that lives next to your current one in
`github.com/fennybz/kcampus-dashboard`. Your existing `app.py`, `db.py` and their
Supabase tables are not changed. Both apps can run side by side.

What's in the folder:

| File | What it does |
| --- | --- |
| `streamlit_app.py` | The Streamlit app. Shows the dashboard full screen and connects it to Supabase. |
| `dashboard.html` | The dashboard itself (Overview, Sales trends, Menu, Prep plan, Insights, Money, Ask AI). |
| `requirements.txt` | Just `streamlit`. |
| `supabase_setup.sql` | Run once in Supabase. Adds one table for uploaded weeks, a private PIN store and two upload functions. |
| `secrets.example.toml` | What to paste into Streamlit's Secrets box. Don't put real keys in GitHub. |

## Step 1: Set up Supabase (5 minutes, one time)

1. Open your Supabase project and go to **SQL Editor > New query**.
2. Paste everything from `supabase_setup.sql`.
3. Find `CHANGE-ME-1234` and replace it with your own upload PIN (6+ characters). Keep the quotes.
4. Click **Run**. You should see "Success".
5. Go to **Project Settings > API** (or **API Keys**) and copy:
   - the **Project URL**
   - the **anon public** key (newer projects call it the **publishable** key, starting `sb_publishable_`)

Use the anon / publishable key, **not** the `service_role` / secret key. The app checks this and refuses a secret key, because the key is sent to every visitor's browser.

If you already ran `supabase_setup.sql` for the GitHub Pages version, skip this step. Both versions share the same data.

## Step 2: Add the folder to GitHub

1. Open github.com/fennybz/kcampus-dashboard.
2. Click **Add file > Upload files**.
3. Drag the whole `dashboard_v2` folder into the page (the folder, not just its files, so they land in `dashboard_v2/`).
4. Click **Commit changes**.

## Step 3: Create the Streamlit app

1. Go to share.streamlit.io and click **Create app** (or **New app**) > **Deploy a public app from GitHub**.
2. Fill in:
   - **Repository:** `fennybz/kcampus-dashboard`
   - **Branch:** `main`
   - **Main file path:** `dashboard_v2/streamlit_app.py`
   - **App URL:** pick a name, e.g. `kalachandjis-dashboard`
3. Open **Advanced settings > Secrets** and paste:

   ```toml
   SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
   SUPABASE_ANON_KEY = "YOUR-ANON-OR-PUBLISHABLE-KEY"
   ```

4. Click **Deploy**. The first start takes 1–2 minutes.

If you forget the secrets, the app still opens, with a blue note saying uploads stay in each browser. Add them later in **App > Settings > Secrets**; the app restarts on its own.

## Step 4: Check it

- The dashboard fills the window with the sidebar on the left.
- No yellow or red note at the top. If there is one, it says what to fix (setup SQL not run, wrong URL, or a secret key).
- Click **Add weekly file**, pick the university's weekly report and enter your PIN. Refresh: the week is still there, and anyone else who opens the link sees it too.

## Weekly routine

1. Open the app and click **Add weekly file**.
2. Pick the university's weekly report (CSV or Excel). Enter the PIN the first time in each browser tab.
3. Everything updates: Overview, alerts, Prep plan, Insights, Money.

Uploading a corrected file for the same week replaces it. To remove one, use **Remove** on **Data & uploads** (PIN needed).

## Updating the dashboard later

When the dashboard gets new features, only `dashboard_v2/dashboard.html` changes. Upload the new file to the same folder on GitHub and commit; Streamlit redeploys in about a minute. Your uploaded weeks stay in Supabase.

## Good to know

- **Who can see it:** a public Streamlit app can be opened by anyone with the link. To restrict it, open **App > Settings > Sharing** and invite specific viewers by email.
- **Ask AI** uses the dashboard's built-in analyst here. It answers the common questions (sales, items, days, prep, add-ons), but it isn't Claude itself. Connecting Claude would need an Anthropic API key and a little server code. Ask if you want it.
- **Changing the PIN:** run this in the Supabase SQL Editor:

  ```sql
  update public.kc_dashboard_settings
  set value = extensions.crypt('NEW-PIN', extensions.gen_salt('bf'))
  where key = 'upload_pin';
  ```

- **Sleeping apps:** free Streamlit apps go to sleep after a few days with no visitors. The first visitor clicks "Yes, get this app back up" and waits about 30 seconds. Data in Supabase isn't affected.
