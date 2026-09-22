import sqlite3
import pandas as pd
import streamlit as st

# Read-only agar tidak bentrok dengan honeypot yang sedang menulis
DB_PATH = 'file:sentinel_data.db?mode=ro'

st.set_page_config(page_title="SentinelTrap | SOC Dashboard", page_icon="🛡️", layout="wide")
st.title("🛡️ SentinelTrap — SOC Dashboard")
st.caption("Real-time SSH honeypot attack monitor | Auto-refresh 5 detik")

def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH, uri=True)
    df = pd.read_sql_query("SELECT * FROM attack_logs ORDER BY id DESC", conn)
    conn.close()
    return df

@st.fragment(run_every=5)   # auto-refresh tiap 5 detik
def live_view():
    df = load_data()

    if df.empty:
        st.info("Belum ada serangan. Jalankan honeypot lalu tes: ssh admin@localhost -p 2222")
        return

    # --- Metric Cards (KPI ala SOC) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Attempts", len(df))
    c2.metric("Unique IPs", df['source_ip'].nunique())
    c3.metric("Unique Usernames", df['username'].nunique())
    c4.metric("Last Attack (UTC)", df['timestamp'].iloc[0])

    st.divider()

    # --- Charts ---
    ch1, ch2 = st.columns(2)
    with ch1:
        st.subheader("Top 10 Source IPs")
        st.bar_chart(df['source_ip'].value_counts().head(10))
    with ch2:
        st.subheader("Top Usernames Dicoba")
        st.bar_chart(df['username'].value_counts().head(10))

    st.subheader("Attack Timeline (per menit)")
    tl = df.copy()
    tl['timestamp'] = pd.to_datetime(tl['timestamp'])
    st.line_chart(tl.set_index('timestamp').resample('1min').size())

    st.divider()

    # --- Raw Logs + Export Evidence ---
    st.subheader("Raw Attack Logs")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export CSV (Evidence)",
                       df.to_csv(index=False).encode('utf-8'),
                       file_name="sentineltrap_evidence.csv")

live_view()