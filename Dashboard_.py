import streamlit as st
import hashlib
from pathlib import Path
from datetime import datetime

# Supabase client helpers (from your supabase_client.py)

from gsheet_client import (
    list_activities_for_user,
    list_all_activities,
    delete_activity,
)

def reset_form_state():
    keys_to_reset = [
        "halaman_awal",
        "blok_1_3",
        "variables",
        "blok_4",
        "blok_5",
        "blok_6_8",
        "indicators",
        "form_data",
        "current_activity_id"
    ]

    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

# --- Function to hash passwords (kept as-is) ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Retrieve credentials from secrets.toml ---
users = st.secrets["users"]
roles = st.secrets["roles"]

# --- Session state for login ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

# --- Login form ---
if not st.session_state.authenticated:
    st.title("🔐 Login")
    username_input = st.text_input("Username")
    password_input = st.text_input("Password", type="password")

    if st.button("Login"):
        if username_input in users and users[username_input] == hash_password(password_input):
            st.session_state.authenticated = True
            st.session_state.username = username_input
            st.session_state.user_id = st.session_state.username
            st.session_state.role = roles.get(username_input, "user")
            st.success(f"Welcome back, {username_input}!")
            st.rerun()
        else:
            st.error("Invalid username atau password")

    st.stop()  # Prevent rest of dashboard until logged in

# --- ✅ Sidebar / Logout (kept as-is) ---
st.sidebar.markdown(f"👤 **Masuk sebagai:** {st.session_state.username}")
st.sidebar.markdown(f"🛡️ **Role:** {st.session_state.role}")
if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.set_page_config(page_title="Kegiatan Statistik", page_icon="📋", layout="wide")

# === Fetch activities from Supabase ===
# For non-verifier: list user's own activities
# For verifier: show submitted activities (you can change to show all if you add list_all in supabase_client)
if st.session_state.role == "verifier":
    activities = list_all_activities()
else:
    activities = list_activities_for_user(st.session_state.user_id)

# st.write("DEBUG - Raw activities from Supabase:", activities)

# Normalize entries into the shape your UI expects (fallbacks for older/local JSON)
form_list = []
for row in activities:
    data = row.get("data") or {}

    activity_id = (
        row.get("activity_id")
        or row.get("id")
        or data.get("activity_id")
    )

    owner = (
        row.get("user_id")
        or data.get("owner")
        or "unknown"
    )

    status = (
        row.get("status")
        or data.get("status")
        or "draft"
    ).title()

    title = (
        data.get("halaman_awal", {}).get("judul")
        or data.get("judul")
        or f"Activity {activity_id}"
    )

    last_saved = (
        data.get("last_saved")
        or row.get("updated_at")
        or "Unknown"
    )

    form_list.append({
        "activity_id": activity_id,
        "owner": owner,
        "status": status,
        "title": title,
        "last_saved": last_saved,
        "raw": row,
    })

# st.write("RAW ACTIVITIES:", activities)

# UI helpers
def status_color(status):
    if status.lower() == "draft":
        return "⚙️"
    elif status.lower() == "submitted":
        return "📤"
    elif status.lower() == "verified":
        return "✅"
    elif status.lower() == "rejected":
        return "❌"
    else:
        return "❓"

st.title("📋 Kegiatan Statistik")
# st.markdown("View and manage your saved or submitted activities below.")

if not form_list:
    st.info("Belum ada Kegiatan Statistik. Klik **Tambah Kegiatan** untuk memulai")
else:
    for idx, item in enumerate(form_list):
        activity_title = item.get("title", "(Tanpa Judul)")
        status = item.get("status", "Draft")
        last_saved = item.get("last_saved", "Unknown")

        with st.expander(f"{status_color(status)} {activity_title}", expanded=False):
            st.write(f"**Status:** {status}")
            st.write(f"**Produsen Data:** {item.get('owner', 'unknown')}")
            st.write(f"**Terakhir Disimpan:** {last_saved}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit", key=f"edit_{idx}"):
                    reset_form_state()
                    # Put the activity id into session and navigate
                    st.session_state.edit_activity_id = item.get("activity_id")
                    st.switch_page("pages/1_Form_Page_.py")
                    st.rerun()

            with col2:
                if st.button("🗑️ Hapus", key=f"delete_{idx}"):
                    aid = item.get("activity_id")
                    if not aid:
                        st.error("Tidak dapat menghapus: activity id tidak terdeteksi")
                    else:
                        ok = delete_activity(aid)
                        if ok:
                            st.success("Terhapus")
                        else:
                            st.error("Gagal menghapus kegiatan")
                        st.rerun()

st.markdown("---")

if st.button("➕ Tambah Kegiatan"):
    reset_form_state()
    st.session_state.edit_activity_id = None
    st.switch_page("pages/1_Form_Page_.py")
