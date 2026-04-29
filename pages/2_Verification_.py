import streamlit as st
from datetime import datetime
from gsheet_client import (
    list_submitted_activities,
    mark_status,
    get_activity,
    upsert_activity
)

st.set_page_config(page_title="Verification Dashboard", page_icon="✅", layout="wide")

# =====================================================
# AUTH CHECK
# =====================================================
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Please log in first.")
    st.stop()

if st.session_state.role != "verifier":
    st.error("⛔ Only verifiers can access this page.")
    st.stop()

if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# =====================================================
# LOAD SUBMITTED ACTIVITIES FROM SUPABASE
# =====================================================
submitted = list_submitted_activities()

st.title("✅ Verification Dashboard")
st.markdown("Review, revise, verify, or reject submitted activities.")

if not submitted:
    st.info("No submitted activities available for verification.")
    st.stop()


# =====================================================
# UTILS (RECURSIVE INPUT EDITOR)
# =====================================================
def edit_value(value, key_path):
    key_str = "_".join(map(str, key_path))

    if isinstance(value, dict):
        st.markdown(f"**{key_path[-1]}**")
        for k, v in value.items():
            value[k] = edit_value(v, key_path + [k])
        return value

    elif isinstance(value, list):
        st.markdown(f"**{key_path[-1]} (list)**")
        for i, item in enumerate(value):
            if isinstance(item, dict):
                value[i] = edit_value(item, key_path + [i])
            else:
                value[i] = st.text_input(
                    f"{key_path[-1]} [{i}]",
                    value=str(item),
                    key="_".join(map(str, key_path + [i]))
                )
        return value

    elif isinstance(value, bool):
        return st.checkbox(key_path[-1], value=value, key=key_str)

    elif isinstance(value, (int, float)):
        return st.number_input(key_path[-1], value=value, key=key_str)

    else:
        return st.text_input(key_path[-1], value=str(value), key=key_str)


# =====================================================
# DISPLAY EACH SUBMITTED ACTIVITY
# =====================================================
for idx, act in enumerate(submitted):
    activity_id = act.get("activity_id")
    data = act.get("data", {})

    title = data.get("halaman_awal", {}).get("judul", f"Untitled {idx}")
    tahun = data.get("halaman_awal", {}).get("tahun", "-")

    with st.expander(f"📄 {title} ({tahun})", expanded=False):

        # --- Allow editing the payload data ---
        for section in ["halaman_awal", "blok_1_3", "variables", "blok_4", "blok_5", "blok_6_8", "indicators"]:
            if section in data:
                data[section] = edit_value(data[section], key_path=[idx, section])

        st.markdown("---")

        col1, col2, col3 = st.columns(3)

        # =====================================================
        # 1️⃣ ACCEPT → VERIFIED
        # =====================================================
        with col1:
            if st.button(f"✅ Accept", key=f"accept_{idx}"):
                data["verified_at"] = datetime.now().isoformat()

                ok, _ = upsert_activity(
                    activity_id=activity_id,
                    user_id=act["user_id"],
                    payload=data,
                    status="verified",
                )

                if ok:
                    st.success(f"✅ {title} verified.")
                    st.rerun()
                else:
                    st.error("❌ Failed to verify.")

        # =====================================================
        # 2️⃣ REQUEST REVISION
        # =====================================================
        with col2:
            revise_note = st.text_area("Revision note", key=f"rev_{idx}")

            if st.button(f"📝 Request Revision", key=f"revbtn_{idx}"):

                if not revise_note.strip():
                    st.error("⚠️ Please provide a revision note.")
                else:
                    # Inject revision metadata
                    data["revision_note"] = revise_note
                    data["revision_requested_at"] = datetime.now().isoformat()

                    ok, _ = upsert_activity(
                        activity_id=activity_id,
                        user_id=act["user_id"],
                        payload=data,
                        status="revision_requested",
                    )

                    if ok:
                        st.warning(f"📝 Sent back for revision: {title}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update revision status.")

        # =====================================================
        # 3️⃣ REJECT
        # =====================================================
        with col3:
            reject_note = st.text_area("Rejection reason", key=f"reject_{idx}")

            if st.button(f"❌ Reject", key=f"rejectbtn_{idx}"):

                if not reject_note.strip():
                    st.error("⚠️ Please provide a rejection reason.")
                else:
                    data["rejection_reason"] = reject_note
                    data["rejected_at"] = datetime.now().isoformat()

                    ok, _ = upsert_activity(
                        activity_id=activity_id,
                        user_id=act["user_id"],
                        payload=data,
                        status="rejected",
                    )

                    if ok:
                        st.error(f"❌ Rejected: {title}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to reject the activity.")
