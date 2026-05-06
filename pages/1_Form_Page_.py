import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from gsheet_client import (get_activity, upsert_activity, mark_status)

def now_jakarta():
    return datetime.now(ZoneInfo("Asia/Jakarta"))

st.set_page_config(page_title="Formulir MS Kegiatan", page_icon="📝", layout="wide")

# =====================================================
# 0️⃣ AUTH CHECK
# =====================================================
if "authenticated" not in st.session_state or not st.session_state.authenticated:
    st.warning("⚠️ Silahkan login untuk mengakses form.")
    st.stop()

if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
    
# =====================================================
# 1️⃣ DEFAULT STATE SETUP
# =====================================================
st.session_state.setdefault("form_data", {})
st.session_state.setdefault("current_activity_id", None)
st.session_state.setdefault("username", "unknown_user")
st.session_state.setdefault("role", "user")

username = st.session_state["username"]
role = st.session_state["role"]

# ===================================================== 
# 2️⃣ HELPER LOAD & SAVE
# ===================================================== 
def load_form(activity_id, username, role): 
    """Ambil data dari temporary base.""" 
    row = get_activity(activity_id) 
    status = row.get("status") if row else "draft"
    
    if not row: 
        return None # wajib cocok owner 

    owner = row.get("user_id")
    if role == "user":
        if username == owner:
            return row.get("data", None)
        return None
    
    # Verifier boleh baca & edit revisi
    if role == "verifier":
        return row.get("data", None)
    
    # Default (should not happen)
    return None

def save_form(activity_id, username, data):
    row = get_activity(activity_id)
    if not row:
        success, row = upsert_activity(
            activity_id=activity_id,
            user_id=username,
            payload=data,
            status="draft"
        )
        return success
    
    owner_id = row.get("user_id")   # ALWAYS USE ORIGINAL OWNER
    success, row = upsert_activity(
        activity_id=activity_id,
        user_id=owner_id,     # <-- fixed
        payload=data,
        status="draft",
    )
    return success
    
def submit_form(activity_id): 
    """Submit final ke temporary table.""" 
    row = get_activity(activity_id)
    owner_id = row.get("user_id")
    
    return upsert_activity(
        activity_id=activity_id,
        user_id=owner_id,   # ALWAYS OWNER
        payload=st.session_state.form_data,
        status="submitted",
    )[0]

# ===================================================== 
# 3️⃣ LOAD STORAGE (EDIT MODE) 
# ===================================================== 
edit_id = st.session_state.get("edit_activity_id") 
is_readonly = False
if edit_id: 
    supa_data = load_form(edit_id, username, role) 
    row = get_activity(edit_id) 
    status = row.get("status")
    notes = row.get("data").get("verifier_comment")
    verif_date = row.get("data").get("revision_requested_at")
    reject_date = row.get("data").get("rejected_at")
    verified_at = row.get("data").get("verified_at")
    if role == "user" and (status == "submitted" or status == "verified" or status == "rejected"):
        is_readonly = True
    
    if supa_data: 
        st.session_state.current_activity_id = edit_id
        st.session_state.form_data = supa_data.copy() 
    else: 
        st.warning("⚠️ Data tidak ditemukan. Membuat draft baru.")
        edit_id = None

# ===================================================== 
# 4️⃣ IF NEW ACTIVITY 
# ===================================================== 
if not edit_id: 
    if not st.session_state.current_activity_id: 
        new_id = str(uuid.uuid4()) 
        st.session_state.current_activity_id = new_id
        save_form(new_id, username, {})
        st.session_state.form_data = {
            "activity_id": new_id,
            "owner": username,
            "status": "draft",
            "last_saved": "",
            "revision_note": "",
            "revision_requested_at": "",
            "rejection_reason": "",
            "verified_by": "",
            "verifier_comment": "",
        }
    
if is_readonly: 
    st.info(f"This activity has been **{status}** and cannot be edited.") 
else: 
    st.success("You can edit and save this activity before submission.")


if edit_id and notes:
    st.info(f"ℹ️ Catatan Revisi:\n{notes}\n\nTanggal Pemeriksaan: {datetime.fromisoformat(verif_date).date().strftime('%d %B %Y')}")

if edit_id and status == "rejected":
    st.warning(f"❌ Alasan Ditolak:\n{notes}\n\nTanggal Ditolak: {datetime.fromisoformat(reject_date).date().strftime('%d %B %Y')}")
elif edit_id and status == "verified":
    st.success(f"✅ Metadata telah diverifikasi dan diterima\n\nTanggal Diterima: {datetime.fromisoformat(verified_at).date().strftime('%d %B %Y')}")

# =====================================================
# 6️⃣ ALWAYS GUARANTEE FORM STRUCTURE (FIXED VERSION)
# =====================================================
sections = [
    "halaman_awal",
    "blok_1_3",
    "variables",
    "blok_4",
    "blok_5",
    "blok_6_8",
    "indicators",
]

for sec in sections:
    # kalau belum ada di data form
    if sec not in st.session_state.form_data:
        st.session_state.form_data[sec] = [] if sec == "variables" else {}

    # kalau belum ada di session_state
    if sec not in st.session_state:
        st.session_state[sec] = st.session_state.form_data[sec]

if st.button("⬅️ Kembali ke Dashboard"):
    st.switch_page("Dashboard_.py")
    st.session_state.pop("edit_activity_id", None)  # optional reset edit mode
    st.rerun()

# ===== Page tabs =====
tab1, tab2, tab3 = st.tabs(["📘 MS Kegiatan", "📊 MS Indikator", "📈 MS Variabel"])

# ============================
# 📘 TAB 1: MS KEGIATAN
# ============================
with tab1:
    st.header("📘 MS Kegiatan")
    st.subheader("🧾 Halaman Awal")

    # 1. Jenis Statistik
    jenis_options = ["Statistik Dasar", "Statistik Sektoral", "Statistik Khusus"]
    stored_value = st.session_state["halaman_awal"].get("jenis_statistik", "")
    jenis_statistik = st.radio(
        "Jenis Statistik",
        jenis_options,
        index = jenis_options.index(stored_value) if stored_value in jenis_options else None,
        key="jenis_statistik",
        horizontal=True,
        disabled = is_readonly
    )
    st.session_state["halaman_awal"]["jenis_statistik"] = jenis_statistik

    # 2. Rekomendasi
    rekomendasi_options = ["Ya", "Tidak"]
    stored_value = st.session_state["halaman_awal"].get("rekomendasi", "")
    rekomendasi = st.radio(
        "Apakah kegiatan ini merupakan rekomendasi?",
        rekomendasi_options,
        index = rekomendasi_options.index(stored_value) if stored_value in rekomendasi_options else None,
        key="rekomendasi",
        horizontal=True,
        disabled = is_readonly            
    )
    st.session_state["halaman_awal"]["rekomendasi"] = rekomendasi

    if rekomendasi == "Ya":
        rekomendasi_id = st.text_input("Masukkan ID Rekomendasi", value=st.session_state["halaman_awal"].get("rekomendasi_id", ""), placeholder="Wajib diisi jika kegiatan ini adalah rekomendasi", disabled = is_readonly
                                      )
    else:
        rekomendasi_id = st.text_input("Masukkan ID Rekomendasi", value="", placeholder="Wajib diisi jika kegiatan ini adalah rekomendasi", disabled = is_readonly)
    st.session_state["halaman_awal"]["rekomendasi_id"] = rekomendasi_id

    # 3. Judul
    judul = st.text_input("Judul Kegiatan", value=st.session_state["halaman_awal"].get("judul", None), key = "judul", disabled = is_readonly)
    st.session_state["halaman_awal"]["judul"] = judul

    # 4. Tahun
    tahun = st.number_input("Tahun", min_value=0, max_value=3000, step=1, value=st.session_state["halaman_awal"].get("tahun", 0), key = "tahun", disabled = is_readonly)
    st.session_state["halaman_awal"]["tahun"] = tahun

    # 5. Cara Pengumpulan
    pengumpulan_options = ["Pencacahan Lengkap", "Survei", "Kompilasi Produk Administrasi", "Cara Lain Sesuai dengan Perkembangan TI"]
    stored_value = st.session_state["halaman_awal"].get("cara_pengumpulan", "")
    cara_pengumpulan = st.selectbox(
        "Cara Pengumpulan Data",
        pengumpulan_options,
        index = pengumpulan_options.index(stored_value) if stored_value in pengumpulan_options else None,
        key="cara_pengumpulan",
        disabled = is_readonly
    )
    st.session_state["halaman_awal"]["cara_pengumpulan"] = cara_pengumpulan

    # 6. Sektor
    sektor_options = ["Pertanian dan Perikanan", "Demografi dan Kependudukan", "Pembangunan", "Proyeksi Ekonomi", "Pendidikan dan Pelatihan",
            "Lingkungan", "Keuangan", "Globalisasi", "Kesehatan", "Industri dan Jasa",
            "Teknologi Informasi dan Komunikasi", "Perdagangan Internasional dan Neraca Perdagangan", "Ketenagakerjaan", "Neraca Nasional",
            "Indikator Ekonomi Bulanan", "Produktivitas", "Harga dan Paritas Daya Beli", 
            "Sektor Publik, Perpajakan, dan Regulasi Pasar", "Perwilayahan dan Perkotaan",
            "Ilmu Pengetahuan dan Hak Paten", "Perlindungan Sosial dan Kesejahteraan", "Transportasi"]
    stored_value = st.session_state["halaman_awal"].get("sektor", "")
    sektor = st.selectbox(
        "Sektor",
        sektor_options,
        index = sektor_options.index(stored_value) if stored_value in sektor_options else None,
        key="sektor",
        disabled = is_readonly
    )
    st.session_state["halaman_awal"]["sektor"] = sektor

    # if submit_halaman_awal: 
    #     new_entry = {
    #         "halaman_awal" : {
    #             "jenis_statistik": jenis_statistik,
    #             "rekomendasi": rekomendasi,
    #             "rekomendasi_id": rekomendasi_id,
    #             "judul": judul,
    #             "tahun": tahun,
    #             "cara_pengumpulan": cara_pengumpulan,
    #             "sektor": sektor,
    #             "status": "Draft",
    #             "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #         }
    #     } 
    #     success = save_form(
    #         activity_id=st.session_state.current_activity_id, 
    #         username=username, 
    #         data=new_entry,) 
        
    #     if success: 
    #         st.success("✅ Tersimpan!") 
    #     else: 
    #         st.error("❌ Gagal menyimpan")
    

    if "blok_1_3" not in st.session_state:
            st.session_state["blok_1_3"] = {}
    
    with st.expander("📘 BLOK 1 – PENYELENGGARA", expanded=False):
    
        # You can later pull these values dynamically from a config file or API if needed
        instansi_default = {
            "i_instansi_penyelenggara": "Kementerian PPN/Bappenas",
            "i_alamat": "Jalan Taman Suropati Nomor 2, Jakarta 10310",
            "i_telepon": "(+6221) 31936207, 3905650",
            "i_faksimile": "(+6221) 3145374",
            "i_email": "-"
        }
        
        # 1.1 Instansi
        st.text_input(
            "1.1 Instansi Penyelenggara",
            value=instansi_default["i_instansi_penyelenggara"],
            disabled=True
        )
        
        # 1.2 Alamat Lengkap (sub-questions)
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Alamat", value=instansi_default["i_alamat"], disabled=True)
            st.text_input("Telepon", value=instansi_default["i_telepon"], disabled=True)
        with col2:
            st.text_input("Faksimile", value=instansi_default["i_faksimile"], disabled=True)
            st.text_input("Email", value=instansi_default["i_email"], disabled=True)

    # st.divider()

    with st.expander("📘 BLOK 2 – PENANGGUNG JAWAB", expanded=False):
        
        st.markdown("#### 2.1 Unit Eselon Penanggung Jawab", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            ii_unit_eselon1 = st.text_input("Eselon I", value=st.session_state["blok_1_3"].get("ii_unit_eselon1", ""), key="ii_unit_eselon1", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_unit_eselon1"] = ii_unit_eselon1
        with col2:
            ii_unit_eselon2 = st.text_input("Eselon II", value=st.session_state["blok_1_3"].get("ii_unit_eselon2", ""), key="ii_unit_eselon2", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_unit_eselon2"] = ii_unit_eselon2
    
        st.markdown("#### 2.2 Penanggung Jawab Teknis", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            ii_pj_nama = st.text_input("Nama", value=st.session_state["blok_1_3"].get("ii_pj_nama", ""), key="ii_pj_nama", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_nama"] = ii_pj_nama
            ii_pj_jabatan = st.text_input("Jabatan", value=st.session_state["blok_1_3"].get("ii_pj_jabatan", ""), key="ii_pj_jabatan", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_jabatan"] = ii_pj_jabatan
            ii_pj_alamat = st.text_area("Alamat", value=st.session_state["blok_1_3"].get("ii_pj_alamat", ""), key="ii_pj_alamat", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_alamat"] = ii_pj_alamat
        with col2:
            ii_pj_telepon = st.text_input("Telepon", value=st.session_state["blok_1_3"].get("ii_pj_telepon", ""), key="ii_pj_telepon", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_telepon"] = ii_pj_telepon
            ii_pj_email = st.text_input("Email", value=st.session_state["blok_1_3"].get("ii_pj_email", ""), key="ii_pj_email", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_email"] = ii_pj_email
            ii_pj_faksimile = st.text_input("Faksimile", value=st.session_state["blok_1_3"].get("ii_pj_faksimile", ""), key="ii_pj_faksimile", disabled = is_readonly)
            st.session_state["blok_1_3"]["ii_pj_faksimile"] = ii_pj_faksimile

    # st.divider()
    
    with st.expander("📘 BLOK 3 – PERENCANAAN DAN PERSIAPAN", expanded=False):
            
        # --- 3.1 Background ---
        st.markdown("#### 3.1 Latar Belakang Kegiatan", unsafe_allow_html=True)
        iii_latar_belakang_kegiatan = st.text_area("Tuliskan latar belakang kegiatan", value=st.session_state["blok_1_3"].get("iii_latar_belakang_kegiatan", ""), key="iii_latar_belakang_kegiatan", disabled = is_readonly)
        st.session_state["blok_1_3"]["iii_latar_belakang_kegiatan"] = iii_latar_belakang_kegiatan
    
        # --- 3.2 Objective ---
        st.markdown("#### 3.2 Tujuan Kegiatan", unsafe_allow_html=True)
        iii_tujuan_kegiatan = st.text_area("Tuliskan tujuan kegiatan", value=st.session_state["blok_1_3"].get("iii_tujuan_kegiatan", ""), key="iii_tujuan_kegiatan", disabled = is_readonly)
        st.session_state["blok_1_3"]["iii_tujuan_kegiatan"] = iii_tujuan_kegiatan
    
        # --- 3.3 Schedule ---
        st.markdown("#### 3.3 Rencana Jadwal Kegiatan", unsafe_allow_html=True)
        st.caption("Isi tanggal mulai dan selesai untuk setiap tahap kegiatan.")
    
        # with st.form("A. Perencanaan"):
        def schedule_row(label, start_key, end_key):
            col1, col_, col2 = st.columns([0.45, 0.1, 0.45])
            with col1:
                st.session_state["blok_1_3"][start_key] = st.date_input(
                    label,
                    value=st.session_state["blok_1_3"].get(start_key, None),
                    key=start_key,
                    disabled = is_readonly
                )
            with col_:
                st.text_input("", value="hingga", disabled=True, key=f"hingga_{label}")
            with col2:
                st.session_state["blok_1_3"][end_key] = st.date_input(
                    "",
                    value=st.session_state["blok_1_3"].get(end_key, None),
                    key=end_key,disabled = is_readonly
                )

        def save_date(start_key, end_key):
            start = st.session_state["blok_1_3"].get(start_key)
            start_date = start.strftime("%d %B %Y") if start else ""
            end = st.session_state["blok_1_3"].get(end_key)
            end_date = end.strftime("%d %B %Y") if end else ""
            date_range = str("Awal: ") + start_date + str(", Akhir: ") + end_date
            return date_range
    
        st.markdown("##### A. Perencanaan", unsafe_allow_html=True)
        schedule_row("1. Perencanaan Kegiatan", "iii_jadwal_perencanaan_kegiatan_start", "iii_jadwal_perencanaan_kegiatan_end")
        st.session_state["blok_1_3"]["iii_jadwal_perencanaan_kegiatan"] = save_date("iii_jadwal_perencanaan_kegiatan_start", "iii_jadwal_perencanaan_kegiatan_end")
        schedule_row("2. Desain", "iii_jadwal_desain_start", "iii_jadwal_desain_end")
        st.session_state["blok_1_3"]["iii_jadwal_desain"] = save_date("iii_jadwal_desain_start", "iii_jadwal_desain_end")
    
        st.markdown("##### B. Pengumpulan", unsafe_allow_html=True)
        schedule_row("3. Pengumpulan Data", "iii_jadwal_pengumpulan_data_start", "iii_jadwal_pengumpulan_data_end")
        st.session_state["blok_1_3"]["iii_jadwal_pengumpulan_data"] = save_date("iii_jadwal_pengumpulan_data_start", "iii_jadwal_pengumpulan_data_end")
        
    
        st.markdown("##### C. Pemeriksaan", unsafe_allow_html=True)
        schedule_row("4. Pengolahan Data", "iii_jadwal_pengolahan_data_start", "iii_jadwal_pengolahan_data_end")
        st.session_state["blok_1_3"]["iii_jadwal_pengolahan_data"] = save_date("iii_jadwal_pengolahan_data_start", "iii_jadwal_pengolahan_data_end")
    
        st.markdown("##### D. Penyebarluasan", unsafe_allow_html=True)
        schedule_row("5. Analisis", "iii_jadwal_analisis_start", "iii_jadwal_analisis_end")
        st.session_state["blok_1_3"]["iii_jadwal_analisis"] = save_date("iii_jadwal_analisis_start", "iii_jadwal_analisis_end")
        schedule_row("6. Diseminasi Hasil", "iii_jadwal_diseminasi_hasil_start", "iii_jadwal_diseminasi_hasil_end")
        st.session_state["blok_1_3"]["iii_jadwal_diseminasi_hasil"] = save_date("iii_jadwal_diseminasi_hasil_start", "iii_jadwal_diseminasi_hasil_end")
        schedule_row("7. Evaluasi", "iii_jadwal_evaluasi_start", "iii_jadwal_evaluasi_end")
        st.session_state["blok_1_3"]["iii_jadwal_evaluasi"] = save_date("iii_jadwal_evaluasi_start", "iii_jadwal_evaluasi_end")
        
        st.markdown("#### 3.4 Variabel")
        st.caption("Tambahkan satu atau lebih variabel berikut dengan informasi lengkap.")
        
        # ✅ Ensure variables list exists but don't reset it every rerun
        if "variables" not in st.session_state or not isinstance(st.session_state.variables, list):
            st.session_state.variables = []
        
        # --- Add new variable ---
        def add_variable():
            st.session_state.variables.append({
                "name": "",
                "concept": "",
                "definition": "",
                "reference": ""
            })
        
        st.button("➕ Tambah Variabel", on_click=add_variable, disabled = is_readonly)
        
        remove_var_index = None
        
        # --- Display existing variables ---
        for i, var in enumerate(st.session_state.variables):
            st.markdown(f"**Variabel {i+1}**")
            with st.container():
                c1, c2 = st.columns(2)
                with c1:
                    st.session_state.variables[i]["name"] = st.text_input(
                        "Nama Variabel", value=var.get("name", ""), key=f"var_name_{i}", disabled = is_readonly
                    )
                    st.session_state.variables[i]["concept"] = st.text_input(
                        "Konsep", value=var.get("concept", ""), key=f"var_concept_{i}", disabled = is_readonly
                    )
                    st.session_state.variables[i]["reference"] = st.text_input(
                        "Referensi Waktu", value=var.get("reference", ""), key=f"var_reference_{i}", disabled = is_readonly
                    )
                with c2:
                    st.session_state.variables[i]["definition"] = st.text_area(
                        "Definisi", value=var.get("definition", ""), key=f"var_definition_{i}", disabled = is_readonly
                    )
        
                if st.button(f"🗑️ Hapus Variabel {i+1}", key=f"remove_var_{i}", disabled = is_readonly):
                    remove_var_index = i
        
        # --- Remove variable if requested ---
        if remove_var_index is not None:
            st.session_state.variables.pop(remove_var_index)
            st.rerun()
    
    if "blok_4" not in st.session_state:
            st.session_state["blok_4"] = {}
    with st.expander("📘 BLOK 4 – DESAIN KEGIATAN", expanded=False):

        # Q4.1 & Q4.2
        frekuensi_options = ["Hanya Sekali", "Harian", "Mingguan", "Bulanan", "Triwulanan", "Empat Bulanan", "Semesteran", "Tahunan", "Lebih dari Dua Tahunan"]
        stored_value = st.session_state["blok_4"].get("iv_frekuensi_penyelenggaraan", "")
        st.markdown("##### 4.1 - 4.2 Frekuensi Penyelenggaraan", unsafe_allow_html=True)
        iv_frekuensi_penyelenggaraan = st.radio(
            "4.2 Frekuensi Penyelenggaraan",
            frekuensi_options, 
            index = frekuensi_options.index(stored_value) if stored_value in frekuensi_options else None,
            key="iv_frekuensi_penyelenggaraan",
            label_visibility = "collapsed",
            horizontal = True,
            disabled = is_readonly
        )

        if iv_frekuensi_penyelenggaraan == "Hanya Sekali":
            iv_kegiatan_ini_dilakukan = "Hanya Sekali"
        else:
            iv_kegiatan_ini_dilakukan = "Berulang"

        st.session_state["blok_4"]["iv_frekuensi_penyelenggaraan"] = iv_frekuensi_penyelenggaraan
        st.session_state["blok_4"]["iv_kegiatan_ini_dilakukan"] = iv_kegiatan_ini_dilakukan

        # Q4.3
        pengumpulan_options = ["Longitudinal Panel", "Longitudinal Cross Sectional", "Cross Sectional"]
        stored_value = st.session_state["blok_4"].get("iv_tipe_pengumpulan_data", "")
        st.markdown("##### 4.3 Tipe Pengumpulan Data", unsafe_allow_html=True)
        iv_tipe_pengumpulan_data = st.radio(
            "4.3 Tipe Pengumpulan Data",
            pengumpulan_options,
            index = pengumpulan_options.index(stored_value) if stored_value in pengumpulan_options else None,
            key="iv_tipe_pengumpulan_data",
            label_visibility = "collapsed",
            horizontal=True,
            disabled = is_readonly
        )
        st.session_state["blok_4"]["iv_tipe_pengumpulan_data"] = iv_tipe_pengumpulan_data

        # Q4.4 & Q4.5
        st.markdown("##### 4.4 - 4.5 Cakupan Wilayah Pengumpulan Data", unsafe_allow_html=True)
        wilayah_options = ['SELURUH WILAYAH INDONESIA', 'ACEH', 'SUMATERA UTARA', 'SUMATERA BARAT', 'RIAU', 'JAMBI', 'SUMATERA SELATAN', 'BENGKULU',
                           'LAMPUNG','KEP. BANGKA BELITUNG', 'KEP. RIAU', 'DKI JAKARTA', 'JAWA BARAT', 'JAWA TENGAH', 'DI YOGYAKARTA', 'JAWA TIMUR',
                           'BANTEN', 'BALI', 'NUSA TENGGARA BARAT', 'NUSA TENGGARA TIMUR', 'KALIMANTAN BARAT', 'KALIMANTAN TENGAH',
                           'KALIMANTAN SELATAN', 'KALIMANTAN TIMUR', 'KALIMANTAN UTARA', 'SULAWESI UTARA', 'SULAWESI TENGAH', 'SULAWESI SELATAN',
                           'SULAWESI TENGGARA', 'GORONTALO', 'SULAWESI BARAT', 'MALUKU', 'MALUKU UTARA', 'PAPUA', 'PAPUA BARAT', 'PAPUA SELATAN',
                           'PAPUA TENGAH', 'PAPUA PEGUNUNGAN', 'PAPUA BARAT DAYA']
        stored_value = st.session_state["blok_4"].get("iv_sebagian_cakupan_wilayah_pengumpulan_data", "")
        iv_sebagian_cakupan_wilayah_pengumpulan_data = st.multiselect(
            "4.5 Wilayah Kegiatan",
            wilayah_options, 
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="iv_sebagian_cakupan_wilayah_pengumpulan_data",
            disabled = is_readonly
        )

        if iv_sebagian_cakupan_wilayah_pengumpulan_data == "SELURUH WILAYAH INDONESIA":
            iv_cakupan_wilayah_pengumpulan_data = "Seluruh Wilayah Indonesia"
        else:
            iv_cakupan_wilayah_pengumpulan_data = "Sebagian Wilayah Indonesia"           
        
        st.session_state["blok_4"]["iv_cakupan_wilayah_pengumpulan_data"] = iv_cakupan_wilayah_pengumpulan_data
        st.session_state["blok_4"]["iv_sebagian_cakupan_wilayah_pengumpulan_data"] = iv_sebagian_cakupan_wilayah_pengumpulan_data

        # Q4.6
        metode_options = ["Wawancara", "Mengisi Kuesioner Sendiri", "Pengamatan", "Pengumpulan Data Sekunder", "Lainnya"]
        stored_value = st.session_state["blok_4"].get("metode_utama", "")
        if isinstance(stored_value, list):
            valid_default = [m for m in stored_value if m in metode_options]
        else:
            valid_default = []
        st.markdown("##### 4.6 Metode Pengumpulan Data", unsafe_allow_html=True)
        metode_utama = st.multiselect(
            "4.6 Metode Pengumpulan Data",
            metode_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="metode_utama",
            disabled = is_readonly
        )
        st.session_state["blok_4"]["metode_utama"] = metode_utama

        metode_lain = st.text_input("Lainnya: Sebutkan metode pengumpulan lain", value=st.session_state["blok_4"].get("metode_lain", ""), key="metode_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'", disabled = is_readonly)
        st.session_state["blok_4"]["metode_lain"] = metode_lain
        iv_metode_pengumpulan_data = metode_utama.copy()
        if "Lainnya" in iv_metode_pengumpulan_data:
            if metode_lain.strip():  # only replace if user actually typed something
                iv_metode_pengumpulan_data = [
                    metode_lain if item == "Lainnya" else item
                    for item in iv_metode_pengumpulan_data
                ]
            else:
                iv_metode_pengumpulan_data.remove("Lainnya")

        st.session_state["blok_4"]["iv_metode_pengumpulan_data"] = iv_metode_pengumpulan_data
        # iv_metode_pengumpulan_data = metode_utama.append(f"Lainnya: {metode_lain}")

        # Q4.7
        sarana_options = ["Paper-assisted Personal Interviewing (PAPI)", "Computer-assisted Personal Interviewing (CAPI)", "Computer-assisted Telephones Interviewing (CATI)", "Computer Aided Web Interviewing (CAWI)", "Mail", "Lainnya"]
        stored_value = st.session_state["blok_4"].get("sarana_utama", "")
        st.markdown("##### 4.7 Sarana Pengumpulan Data", unsafe_allow_html=True)
        sarana_utama = st.multiselect(
            "4.7 Sarana Pengumpulan Data",
            sarana_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="sarana_utama",
            disabled = is_readonly
        )
        st.session_state["blok_4"]["sarana_utama"] = sarana_utama

        sarana_lain = st.text_input("Lainnya: Sebutkan sarana pengumpulan lain", value=st.session_state["blok_4"].get("sarana_lain", ""), key="sarana_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'", disabled = is_readonly)
        st.session_state["blok_4"]["sarana_lain"] = sarana_lain
        iv_sarana_pengumpulan_data = sarana_utama.copy()
        if "Lainnya" in iv_sarana_pengumpulan_data:
            if sarana_lain.strip():  # only replace if user actually typed something
                iv_sarana_pengumpulan_data = [
                    sarana_lain if item == "Lainnya" else item
                    for item in iv_sarana_pengumpulan_data
                ]
            else:
                iv_sarana_pengumpulan_data.remove("Lainnya")

        st.session_state["blok_4"]["iv_sarana_pengumpulan_data"] = iv_sarana_pengumpulan_data

        # Q4.8
        unit_options = ["Individu", "Rumah Tangga", "Usaha/Perusahaan", "Lainnya"]
        stored_value = st.session_state["blok_4"].get("unit_utama", "")
        st.markdown("##### 4.8 Unit Pengumpulan Data", unsafe_allow_html=True)
        unit_utama = st.multiselect(
            "4.8 Unit Pengumpulan Data",
            unit_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="unit_utama",
            disabled = is_readonly
        )
        st.session_state["blok_4"]["unit_utama"] = unit_utama

        unit_lain = st.text_input("Lainnya: Sebutkan unit pengumpulan lain", value=st.session_state["blok_4"].get("unit_lain", ""), key="unit_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'", disabled = is_readonly)
        st.session_state["blok_4"]["unit_lain"] = unit_lain
        iv_unit_pengumpulan_data = unit_utama.copy()
        if "Lainnya" in iv_unit_pengumpulan_data:
            if unit_lain.strip():  # only replace if user actually typed something
                iv_unit_pengumpulan_data = [
                    unit_lain if item == "Lainnya" else item
                    for item in iv_unit_pengumpulan_data
                ]
            else:
                iv_unit_pengumpulan_data.remove("Lainnya")

        st.session_state["blok_4"]["iv_unit_pengumpulan_data"] = iv_unit_pengumpulan_data

    if "blok5" not in st.session_state:
        st.session_state["blok5"] = {}
    
    # --- CONDITIONAL BLOCK 5 ---
    if st.session_state["halaman_awal"].get("cara_pengumpulan") == "Survei":
        with st.expander("📘 BLOK 5 - DESAIN SAMPEL", expanded=False):        
    
            # 5.1 Jenis Rancangan Sampel
            rancangan_options = ["Single Stage atau Phase Dasar", "Multi Stage atau Phase"]
            stored_value = st.session_state["blok_5"].get("v_jenis_rancangan_sampel", "")
            st.markdown("##### 5.1 Jenis Rancangan Sampel")
            v_jenis_rancangan_sampel = st.radio(
                "5.1 Jenis Rancangan Sampel",
                rancangan_options,
                index = rancangan_options.index(stored_value) if stored_value in rancangan_options else None,
                key="v_jenis_rancangan_sampel",
                label_visibility = "collapsed",
                horizontal=True,
                disabled = is_readonly
            )
            st.session_state["blok_5"]["v_jenis_rancangan_sampel"] = v_jenis_rancangan_sampel
    
            # 5.2 Metode Pemilihan Sampel Tahap Terakhir
            stored_sampel_prob = st.session_state["blok_5"].get("sampel_prob", "")
            stored_sampel_nonprob = st.session_state["blok_5"].get("sampel_nonprob", "")
            st.markdown("##### 5.2 Metode Pemilihan Sampel Tahap Terakhir")
            st.markdown("Pilih salah satu")
            sampel_prob = st.checkbox("Sampel Probabilitas", value=st.session_state["blok_5"].get("sampel_prob", ""), disabled = is_readonly)
            sampel_nonprob = st.checkbox("Sampel Nonprobabilitas", value=st.session_state["blok_5"].get("sampel_nonprob", ""), disabled = is_readonly)
            st.session_state["blok_5"]["sampel_prob"] = sampel_prob
            st.session_state["blok_5"]["sampel_nonprob"] = sampel_nonprob
    
            # 5.2 Metode Pemilihan Sampel Tahap Terakhir
            v_kerangka_sampel_tahap_akhir = ""
            v_metode_yang_digunakan = ""
            v_fraksi_sampel_keseluruhan = ""
            v_nilai_perkiraan_sampling_error_variabel_utama = ""
            if sampel_prob:
                st.session_state["blok_5"]["pemilihan_sampel"] = "Sampel Probabilitas"
                prob_options = ["Simple Random Sampling", "Systematic Random Sampling", "Stratified Random Sampling", "Cluster Sampling",
                               "Probability Proportional to Size Sampling"] 
                stored_value = st.session_state["blok_5"].get("v_metode_yang_digunakan", "")
                st.markdown("##### 5.3 Metode yang Digunakan")
                v_metode_yang_digunakan = st.radio(
                    "5.3 Metode yang Digunakan",
                    prob_options,
                    index = prob_options.index(stored_value) if stored_value in prob_options else None,
                    key="v_metode_yang_digunakan",
                    label_visibility = "collapsed",
                    horizontal=True,
                    disabled = is_readonly
                )
                st.session_state["blok_5"]["v_metode_yang_digunakan"] = v_metode_yang_digunakan
    
                kerangka_options = ["List Frame", "Area Frame"] 
                stored_value = st.session_state["blok_5"].get("v_kerangka_sampel_tahap_akhir", "")
                st.markdown("##### 5.4 Kerangka Sampel Tahap Terakhir")
                v_kerangka_sampel_tahap_akhir = st.radio(
                    "5.3 Metode yang Digunakan",
                    kerangka_options,
                    index = kerangka_options.index(stored_value) if stored_value in kerangka_options else None,
                    key="v_kerangka_sampel_tahap_akhir",
                    label_visibility = "collapsed",
                    horizontal=True,
                    disabled = is_readonly
                )
                st.session_state["blok_5"]["v_kerangka_sampel_tahap_akhir"] = v_kerangka_sampel_tahap_akhir
    
                st.markdown("#### 5.5 Fraksi Sampel Keseluruhan", unsafe_allow_html=True)
                v_fraksi_sampel_keseluruhan = st.text_area("Tuliskan latar belakang kegiatan",
                                                           value=st.session_state["blok_5"].get("v_fraksi_sampel_keseluruhan", ""),
                                                           label_visibility = "collapsed",
                                                           placeholder = "Tuliskan fraksi sampel keseluruhan",
                                                           key="v_fraksi_sampel_keseluruhan",
                                                          disabled = is_readonly)
                st.session_state["blok_5"]["v_fraksi_sampel_keseluruhan"] = v_fraksi_sampel_keseluruhan
    
                st.markdown("#### 5.6 Nilai Perkiraan Sampling Error Variabel Utama", unsafe_allow_html=True)
                v_nilai_perkiraan_sampling_error_variabel_utama = st.text_area("5.6 Nilai Perkiraan Sampling Error Variabel Utama", 
                                                                        value=st.session_state["blok_5"].get("v_nilai_perkiraan_sampling_error_variabel_utama", ""),
                                                                        label_visibility = "collapsed",
                                                                        placeholder = "Tuliskan nilai perkiraan sampling error variabel utama",
                                                                        key="v_nilai_perkiraan_sampling_error_variabel_utama",
                                                                              disabled = is_readonly)
                st.session_state["blok_5"]["v_nilai_perkiraan_sampling_error_variabel_utama"] = v_nilai_perkiraan_sampling_error_variabel_utama
    
            if sampel_nonprob:
                st.session_state["blok_5"]["pemilihan_sampel"] = "Sampel Nonprobabilitas"
                nonprob_options = ["Quota Sampling", "Accidental Sampling", "Purposive Sampling", "Snowball Sampling", "Saturation Sampling"] 
                stored_value = st.session_state["blok_5"].get("v_metode_yang_digunakan", "")
                st.markdown("##### 5.3 Metode yang Digunakan")
                v_metode_yang_digunakan = st.radio(
                    "5.3 Metode yang Digunakan",
                    nonprob_options,
                    index = nonprob_options.index(stored_value) if stored_value in nonprob_options else None,
                    key="v_metode_yang_digunakan",
                    label_visibility = "collapsed",
                    horizontal=True,
                    disabled = is_readonly
                )
                st.session_state["blok_5"]["v_metode_yang_digunakan"] = v_metode_yang_digunakan
    
            st.markdown("#### 5.7 Unit Sampel", unsafe_allow_html=True)
            v_unit_sampel = st.text_area("5.7 Unit Sampel", value=st.session_state["blok_5"].get("v_unit_sampel", ""), label_visibility = "collapsed",
                                         placeholder = "Tuliskan unit sampel", key="v_unit_sampel", disabled = is_readonly)
            st.session_state["blok_5"]["v_unit_sampel"] = v_unit_sampel
    
            st.markdown("#### 5.8 Unit Observasi", unsafe_allow_html=True)
            v_unit_observasi = st.text_area("5.8 Unit Observasi", value=st.session_state["blok_5"].get("v_unit_observasi", ""), label_visibility = "collapsed",
                                         placeholder = "Tuliskan unit observasi", key="v_unit_observasi", disabled = is_readonly)
            st.session_state["blok_5"]["v_unit_observasi"] = v_unit_observasi
    
    else:
        st.info("➡️ Karena cara pengumpulan bukan 'Survei', BLOK 5 dilewati. Silakan lanjut ke BLOK 6.")

    # st.divider()

    if "blok_6_8" not in st.session_state:
            st.session_state["blok_6_8"] = {}
    
    with st.expander("📘 BLOK 6 – PENGUMPULAN DATA", expanded=False):

        col1, col2 = st.columns(2)

        #Q6.1
        with col1:
            stored_value = st.session_state["blok_6_8"].get("vi_apakah_melakukan_uji_coba", "")
            vi_apakah_melakukan_uji_coba = st.checkbox("Melakukan Uji Coba (Pilot Survey)", value=st.session_state["blok_6_8"].get("vi_apakah_melakukan_uji_coba", ""), disabled = is_readonly)
            st.session_state["blok_6_8"]["vi_apakah_melakukan_uji_coba"] = vi_apakah_melakukan_uji_coba

        #Q6.3
        with col2:

            stored_value = st.session_state["blok_6_8"].get("vi_apakah_melakukan_penyesuaian_nonrespon", "")
            vi_apakah_melakukan_penyesuaian_nonrespon = st.checkbox("Melakukan Penyesuaian Nonrespon",
                                                                    value=st.session_state["blok_6_8"].get("vi_apakah_melakukan_penyesuaian_nonrespon", ""), disabled = is_readonly)
            st.session_state["blok_6_8"]["vi_apakah_melakukan_penyesuaian_nonrespon"] = vi_apakah_melakukan_penyesuaian_nonrespon
            
        
        #Q6.2
        qc_options = ["Kunjungan Kembali", "Supervisi", "Task Force", "Lainnya"]
        stored_value = st.session_state["blok_6_8"].get("qc_utama", "")
        st.markdown("##### 6.2 Metode Pemeriksaan Kualitas Pengumpulan Data", unsafe_allow_html=True)
        qc_utama = st.multiselect(
            "6.2 Metode Pemeriksaan Kualitas Pengumpulan Data",
            qc_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="vi_metode_pemeriksaan_kualitas_pengumpulan_data",
            disabled = is_readonly
        )
        st.session_state["blok_6_8"]["qc_utama"] = qc_utama

        qc_lain = st.text_input("Lainnya: Sebutkan metode pemeriksaan kualitas lain", value=st.session_state["blok_6_8"].get("qc_lain", ""), key="qc_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'", disabled = is_readonly)
        st.session_state["blok_6_8"]["qc_lain"] = qc_lain
        vi_metode_pemeriksaan_kualitas_pengumpulan_data = qc_utama.copy()
        if "Lainnya" in vi_metode_pemeriksaan_kualitas_pengumpulan_data:
            if qc_lain.strip():  # only replace if user actually typed something
                vi_metode_pemeriksaan_kualitas_pengumpulan_data = [
                    qc_lain if item == "Lainnya" else item
                    for item in vi_metode_pemeriksaan_kualitas_pengumpulan_data
                ]
            else:
                vi_metode_pemeriksaan_kualitas_pengumpulan_data.remove("Lainnya")

        st.session_state["blok_6_8"]["vi_metode_pemeriksaan_kualitas_pengumpulan_data"] = vi_metode_pemeriksaan_kualitas_pengumpulan_data

        interview_based = ["Paper-assisted Personal Interviewing (PAPI)", "Computer-assisted Personal Interviewing (CAPI)",
                           "Computer-assisted Telephones Interviewing (CATI)"]
        
        # Check if user selected one of the interview-based methods
        vi_petugas_pengumpulan_data = ""
        vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data = ""
        vi_jumlah_petugas_supervisor = 0
        vi_jumlah_petugas_enumerator = 0
        if any(opt in st.session_state["blok_4"].get("sarana_utama") for opt in interview_based):
            #Q6.4
            st.markdown("##### 6.4 Petugas Pengumpulan Data")
            petugas_options = ["Staf Instansi Penyelenggara", "Mitra Atau Tenaga Kontrak", "Staf Instansi Penyelenggara & Mitra Atau Tenaga Kontrak"] 
            stored_value = st.session_state["blok_6_8"].get("vi_petugas_pengumpulan_data", "")
            vi_petugas_pengumpulan_data = st.radio(
                "6.4 Petugas Pengumpulan Data",
                petugas_options,
                index = petugas_options.index(stored_value) if stored_value in petugas_options else None,
                key="vi_petugas_pengumpulan_data",
                label_visibility = "collapsed",
                horizontal=True,
                disabled = is_readonly
            )
            st.session_state["blok_6_8"]["vi_petugas_pengumpulan_data"] = vi_petugas_pengumpulan_data

            #Q6.5
            st.markdown("##### 6.5 Persyaratan Pendidikan Terendah Petugas Pengumpulan Data")
            petugas_options = ["Kurang Dari Atau Sama Dengan SMP", "SMA Atau SMK", "Diploma I/II/III", "Diploma IV atau S1/S2/S3"] 
            stored_value = st.session_state["blok_6_8"].get("vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data", "")
            vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data = st.radio(
                "6.5 Persyaratan Pendidikan Terendah Petugas Pengumpulan Data",
                petugas_options,
                index = petugas_options.index(stored_value) if stored_value in petugas_options else None,
                key="vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data",
                label_visibility = "collapsed",
                horizontal=True,
                disabled = is_readonly
            )
            st.session_state["blok_6_8"]["vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data"] = vi_persyaratan_pendidikan_terendah_petugas_pengumpulan_data

            #Q6.6
            st.markdown("##### 6.6 Jumlah Petugas")
            vi_jumlah_petugas_supervisor = st.number_input("Supervisor/Penyelia/Pengawas", min_value=0, max_value=3000, step=1, value=st.session_state["blok_6_8"].get("vi_jumlah_petugas_supervisor", None), key = "vi_jumlah_petugas_supervisor", disabled = is_readonly)
            st.session_state["blok_6_8"]["vi_jumlah_petugas_supervisor"] = vi_jumlah_petugas_supervisor
            vi_jumlah_petugas_enumerator = st.number_input("Pengumpul Data/Enumerator", min_value=0, max_value=3000, step=1, value=st.session_state["blok_6_8"].get("vi_jumlah_petugas_enumerator", None), key = "vi_jumlah_petugas_enumerator", placeholder = "Tidak boleh kurang dari jumlah Supervisor/Penyelia/Pengawas", disabled = is_readonly)
            st.session_state["blok_6_8"]["vi_jumlah_petugas_enumerator"] = vi_jumlah_petugas_enumerator          

        #Q6.7
        stored_value = st.session_state["blok_6_8"].get("vi_apakah_melakukan_pelatihan_petugas", "")
        vi_apakah_melakukan_pelatihan_petugas = st.checkbox("Melakukan Pelatihan Tugas",
                                                                value=st.session_state["blok_6_8"].get("vi_apakah_melakukan_pelatihan_petugas", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["vi_apakah_melakukan_pelatihan_petugas"] = vi_apakah_melakukan_pelatihan_petugas      
   
    # st.divider()
    
    with st.expander("📘 BLOK 7 – PENGOLAHAN DAN ANALISIS", expanded=False):

        #Q7.1
        tahapan_list = []
        st.markdown("##### 7.1 Tahapan Pengolahan Data")
        stored_value = st.session_state["blok_6_8"].get("penyuntingan", "")
        penyuntingan = st.checkbox("Penyuntingan (Editing)", value=st.session_state["blok_6_8"].get("penyuntingan", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["penyuntingan"] = penyuntingan
        if penyuntingan:
            tahapan_list.append("Penyuntingan (Editing)")

        stored_value = st.session_state["blok_6_8"].get("penyandian", "")
        penyandian = st.checkbox("Penyandian (Coding)", value=st.session_state["blok_6_8"].get("penyandian", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["penyandian"] = penyandian
        if penyandian:
            tahapan_list.append("Penyandian (Coding)")
        
        stored_value = st.session_state["blok_6_8"].get("entry", "")
        entry = st.checkbox("Data Entry", value=st.session_state["blok_6_8"].get("entry", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["entry"] = entry
        if entry:
            tahapan_list.append("Data Entry")

        st.session_state["blok_6_8"]["vii_tahapan_pengolahan_data"] = tahapan_list

        stored_value = st.session_state["blok_6_8"].get("penyahihan", "")
        penyahihan = st.checkbox("Penyahihan (Validasi)", value=st.session_state["blok_6_8"].get("penyahihan", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["penyahihan"] = penyahihan
        if penyahihan:
            tahapan_list.append("Penyahihan (Validasi)")

        #Q7.2
        st.markdown("##### 7.2 Metode Analisis")
        analisis_options = ["Deskriptif", "Inferensia", "Deskriptif dan Inferensia"] 
        stored_value = st.session_state["blok_6_8"].get("vii_metode_analisis", "")
        vii_metode_analisis = st.radio(
            "7.2 Metode Analisis",
            analisis_options,
            index = analisis_options.index(stored_value) if stored_value in analisis_options else None,
            key="vii_metode_analisis",
            label_visibility = "collapsed",
            horizontal=True,
            disabled = is_readonly
        )
        st.session_state["blok_6_8"]["vii_metode_analisis"] = vii_metode_analisis

        #Q7.3
        unit_analisis_options = ["Individu", "Rumah Tangga", "Usaha/Perusahaan", "Lainnya"]
        stored_value = st.session_state["blok_6_8"].get("unit_analisis_utama", "")
        st.markdown("##### 7.3 Unit Analisis", unsafe_allow_html=True)
        unit_analisis_utama = st.multiselect(
            "7.3 Unit Analisis",
            unit_analisis_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="unit_analisis_utama",
            disabled = is_readonly
        )
        st.session_state["blok_6_8"]["unit_analisis_utama"] = unit_analisis_utama

        unit_analisis_lain = st.text_input("Lainnya: Sebutkan unit analisis lain", value=st.session_state["blok_6_8"].get("unit_analisis_lain", ""), key="unit_analisis_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'")
        st.session_state["blok_6_8"]["unit_analisis_lain"] = unit_analisis_lain

        vii_unit_analisis = unit_analisis_utama.copy()
        if "Lainnya" in vii_unit_analisis:
            if unit_analisis_lain.strip():  # only replace if user actually typed something
                vii_unit_analisis = [
                    unit_analisis_lain if item == "Lainnya" else item
                    for item in vii_unit_analisis
                ]
            else:
                vii_unit_analisis.remove("Lainnya")

        st.session_state["blok_6_8"]["vii_unit_analisis"] = vii_unit_analisis

        #Q7.4
        penyajian_options = ["Nasional", "Provinsi", "Kabupaten/Kota", "Lainnya"]
        stored_value = st.session_state["blok_6_8"].get("penyajian_utama", "")
        st.markdown("##### 7.4  Tingkat Penyajian Hasil Analisis", unsafe_allow_html=True)
        penyajian_utama = st.multiselect(
            "7.4  Tingkat Penyajian Hasil Analisis",
            penyajian_options,
            default = stored_value if isinstance(stored_value, list) else [],
            label_visibility = "collapsed",
            key="penyajian_utama",
            disabled = is_readonly
        )
        st.session_state["blok_6_8"]["penyajian_utama"] = penyajian_utama

        penyajian_lain = st.text_input("Lainnya: Sebutkan tingkat penyajian lain", value=st.session_state["blok_6_8"].get("penyajian_lain", ""), key="penyajian_lain", placeholder = "Wajib diisi jika memilih opsi 'Lainnya'")
        st.session_state["blok_6_8"]["penyajian_lain"] = penyajian_lain

        vii_tingkat_penyajian_hasil_analisis = penyajian_utama.copy()
        if "Lainnya" in vii_tingkat_penyajian_hasil_analisis:
            if penyajian_lain.strip():  # only replace if user actually typed something
                vii_tingkat_penyajian_hasil_analisis = [
                    penyajian_lain if item == "Lainnya" else item
                    for item in vii_tingkat_penyajian_hasil_analisis
                ]
            else:
                vii_tingkat_penyajian_hasil_analisis.remove("Lainnya")

        st.session_state["blok_6_8"]["vii_tingkat_penyajian_hasil_analisis"] = vii_tingkat_penyajian_hasil_analisis
    
    with st.expander("📘 BLOK 8 – DISEMINASI HASIL", expanded=False):

        #Q8.1
        st.markdown("##### 8.1 Produk Kegiatan yang Tersedia untuk Umum")
        stored_value = st.session_state["blok_6_8"].get("viii_ketersediaan_produk_tercetak", "")
        viii_ketersediaan_produk_tercetak = st.checkbox("Tercetak (Hardcopy)", value=st.session_state["blok_6_8"].get("viii_ketersediaan_produk_tercetak", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["viii_ketersediaan_produk_tercetak"] = viii_ketersediaan_produk_tercetak
        viii_rencana_jadwal_rilis_produk_tercetak = ""
        if viii_ketersediaan_produk_tercetak:
            viii_rencana_jadwal_rilis_produk_tercetak = st.date_input("8.2 Rencana Rilis Produk Kegiatan", value=st.session_state["blok_6_8"].get("viii_rencana_jadwal_rilis_produk_tercetak", None), key="viii_rencana_jadwal_rilis_produk_tercetak", disabled = is_readonly)
            st.session_state["blok_6_8"]["viii_rencana_jadwal_rilis_produk_tercetak"] = viii_rencana_jadwal_rilis_produk_tercetak

        stored_value = st.session_state["blok_6_8"].get("viii_ketersediaan_produk_digital", "")
        viii_ketersediaan_produk_digital = st.checkbox("Digital (Softcopy)", value=st.session_state["blok_6_8"].get("viii_ketersediaan_produk_digital", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["viii_ketersediaan_produk_digital"] = viii_ketersediaan_produk_digital
        viii_rencana_jadwal_rilis_produk_digital = ""
        if viii_ketersediaan_produk_digital:
            viii_rencana_jadwal_rilis_produk_digital = st.date_input("8.2 Rencana Rilis Produk Kegiatan", value=st.session_state["blok_6_8"].get("viii_rencana_jadwal_rilis_produk_digital", None), key="viii_rencana_jadwal_rilis_produk_digital", disabled = is_readonly)
            st.session_state["blok_6_8"]["viii_rencana_jadwal_rilis_produk_digital"] = viii_rencana_jadwal_rilis_produk_digital

        stored_value = st.session_state["blok_6_8"].get("viii_ketersediaan_produk_mikrodata", "")
        viii_ketersediaan_produk_mikrodata = st.checkbox("Data Mikro", value=st.session_state["blok_6_8"].get("viii_ketersediaan_produk_mikrodata", ""), disabled = is_readonly)
        st.session_state["blok_6_8"]["viii_ketersediaan_produk_mikrodata"] = viii_ketersediaan_produk_mikrodata
        viii_rencana_jadwal_rilis_produk_mikrodata = ""
        if viii_ketersediaan_produk_mikrodata:
            viii_rencana_jadwal_rilis_produk_mikrodata= st.date_input("8.2 Rencana Rilis Produk Kegiatan", value=st.session_state["blok_6_8"].get("viii_rencana_jadwal_rilis_produk_mikrodata", None), key="viii_rencana_jadwal_rilis_produk_mikrodata", disabled = is_readonly)
            st.session_state["blok_6_8"]["viii_rencana_jadwal_rilis_produk_mikrodata"] = viii_rencana_jadwal_rilis_produk_mikrodata

with tab2:
    st.header("📊 MS Indikator")
    if "indicators" not in st.session_state or not isinstance(st.session_state.indicators, list):
        # If it's an empty dict or string from old saves, reset to []
        st.session_state.indicators = []
        
        # Add a new indicators
    if st.button("➕ Tambah Indikator", disabled = is_readonly):
        st.session_state.indicators.append({
            "nama": "",
            "definisi": "",
            "konsep": "",
            "interpretasi": "",
            "metode": "",
            "ukuran": "",
            "satuan": "",
            "klasifikasi_penyajian": "",
            "indikator_komposit": False,
            "indikator_pembangun": [],
            "variabel_pembangun": [],
            "level_estimasi": "",
            "indikator_diakses_umum": ""               
        })
    
    # Track which variable to remove
    remove_ind_index = None
    
    # Safety: handle string corruption case
    if isinstance(st.session_state.indicators, str):
        try:
            st.session_state.indicators = json.loads(st.session_state.indicators)
        except json.JSONDecodeError:
            st.session_state.indicators = []
    
    # Display all variables
    for i, ind in enumerate(st.session_state.indicators):
        ind.setdefault("indikator_pembangun", [])
        ind.setdefault("variabel_pembangun", [])
        with st.expander(f"📘 Indikator {i+1}: {ind.get('nama', '(Belum diisi)')}"):
            ind["nama"] = st.text_input(
                "Nama Indikator", value=ind.get("nama", ""), key=f"ind_nama_{i}", disabled = is_readonly
            )
            ind["definisi"] = st.text_area(
                "Definisi", value=ind.get("definisi", ""), key=f"ind_definisi_{i}", disabled = is_readonly
            )
            ind["konsep"] = st.text_input(
                "Konsep", value=ind.get("konsep", ""), key=f"ind_konsep_{i}", disabled = is_readonly
            )
            ind["interpretasi"] = st.text_area(
                "Interpretasi", value=ind.get("interpretasi", ""), key=f"ind_interpretasi_{i}", disabled = is_readonly
            )
            ind["metode"] = st.text_input(
                "Metode", value=ind.get("metode", ""), key=f"ind_metode_{i}", disabled = is_readonly
            )
            ind["ukuran"] = st.text_input(
                "Ukuran", value=ind.get("ukuran", ""), key=f"ind_ukuran_{i}", disabled = is_readonly
            )
            ind["satuan"] = st.text_input(
                "Satuan", value=ind.get("satuan", ""), key=f"ind_satuan_{i}", disabled = is_readonly
            )
            ind["klasifikasi_penyajian"] = st.text_input(
                "Klasifikasi Penyajian", value=ind.get("klasifikasi_penyajian", ""), key=f"ind_klasifikasi_penyajian_{i}", disabled = is_readonly
            )
            ind["indikator_komposit"] = st.checkbox(
                "Merupakan Indikator Komposit", value=ind.get("indikator_komposit", False), key=f"ind_indikator_komposit_{i}", disabled = is_readonly
            )

            #================================
            # CASE 1: Indikator Komposit
            #================================
            if ind["indikator_komposit"]:
                st.caption("Jika merupakan indikator komposit, tambahkan satu atau lebih indikator pembangun")
                with st.popover("Indikator Pembangun"):  
                    if st.button("➕ Tambah Indikator Pembangun", key = f"add_ind_build_{i}", disabled = is_readonly):
                        ind["indikator_pembangun"].append({
                            "nama_indikator_pembangun": "",
                            "publikasi_ketersediaan": ""
                        })
    
                    remove_sub_index = None
                    for j, sub in enumerate(ind["indikator_pembangun"]):
                        st.markdown(f"🔹 Indikator Pembangun {j+1}")
                        col1, col2 = st.columns(2)
                        with col1:
                            sub["nama_indikator_pembangun"] = st.text_input("Nama Indikator Pembangun", value = sub.get("nama_indikator_pembangun", ""), key = f"ind_build_name_{i}_{j}", disabled = is_readonly
                                                                           )
                        with col2:
                            sub["publikasi_ketersediaan"] = st.text_input("Publikasi Ketersediaan", value = sub.get("publikasi_ketersediaan", ""), key = f"ind_avail_pub{i}_{j}", disabled = is_readonly
                                                                         )
                        if st.button(f"🗑️ Hapus Indikator Pembangun {j+1}", key=f"remove_build_{i}_{j}", disabled = is_readonly):
                            remove_sub_index = j
    
                    if remove_sub_index is not None:
                        ind["indikator_pembangun"].pop(remove_sub_index)
    
            else:
                st.caption("Jika bukan merupakan indikator komposit, tambahkan satu atau lebih variabel pembangun")
                with st.popover("Variabel Pembangun"):
                    if st.button("➕ Tambah Variabel Pembangun", key=f"add_var_build_{i}", disabled = is_readonly):
                        ind["variabel_pembangun"].append({
                            "nama_variabel_pembangun": "",
                            "kegiatan_penghasil": ""
                        })
        
                    remove_var_index = None
                    for j, var in enumerate(ind["variabel_pembangun"]):
                        st.markdown(f"🔹 Variabel Pembangun {j+1}")
                        col1, col2 = st.columns(2)
                        with col1:
                            var["nama_variabel_pembangun"] = st.text_input(
                                "Nama Variabel Pembangun",
                                value=var.get("nama_variabel_pembangun", ""),
                                key=f"var_build_name_{i}_{j}", disabled = is_readonly
                            )
                        with col2:
                            var["kegiatan_penghasil"] = st.text_input(
                                "Kegiatan Penghasil Variabel",
                                value=var.get("kegiatan_penghasil", ""),
                                key=f"var_build_source_{i}_{j}", disabled = is_readonly
                            )
        
                        if st.button(f"🗑️ Hapus Variabel Pembangun {j+1}", key=f"remove_var_{i}_{j}", disabled = is_readonly):
                            remove_var_index = j
        
                    if remove_var_index is not None:
                        ind["variabel_pembangun"].pop(remove_var_index)
            
            ind["level_estimasi"] = st.text_area(
                "Level Estimasi", value=ind.get("level_estimasi", ""), key=f"ind_level_estimasi_{i}", disabled = is_readonly
            )
            ind["indikator_diakses_umum"] = st.checkbox(
                "Indikator Dapat Diakses Umum", value=ind.get("indikator_diakses_umum", False), key=f"ind_dapat_diakses_umum_{i}", disabled = is_readonly
            )            
            # Remove variable button
            if st.button(f"🗑️ Hapus Indikator {i+1}", key=f"remove_ind_{i}", disabled = is_readonly):
                remove_ind_index = i
      
            st.divider()
    
    # Actually remove the indicators after the loop
    if remove_ind_index is not None:
        st.session_state.indicators.pop(remove_ind_index)

with tab3:
    st.header("📈 MS Variabel")
    if "variables" in st.session_state and isinstance(st.session_state.variables, list) and len(st.session_state.variables) > 0:
        for i, var in enumerate(st.session_state.variables):
    
            with st.container():
                with st.expander(f"📘 Variabel {i+1}: {var.get('name', '(Belum diisi)')}"):
                    alias = st.text_input(
                        "Alias",
                        value=var.get("alias", ""),
                        key=f"alias_{i}", disabled = is_readonly
                    )
                    var["alias"] = alias  # store in session_state
                    
                    st.write(f"**Definisi Variabel:** {var.get('definition', '-')}")
                    st.write(f"**Konsep:** {var.get('concept', '-')}")
                    st.write(f"**Referensi Waktu:** {var.get('reference', '-')}")
                    
                    referensi_pemilihan = st.text_input(
                        "Referensi Pemilihan",
                        value=var.get("referensi_pemilihan", ""),
                        key=f"referensi_pemilihan_{i}", disabled = is_readonly
                    )
                    var["referensi_pemilihan"] = referensi_pemilihan  # store in session_state
                    
                    ukuran = st.text_input(
                        "Ukuran",
                        value=var.get("ukuran", ""),
                        key=f"ukuran_{i}", disabled = is_readonly
                    )
                    var["ukuran"] = ukuran  # store in session_state
                    
                    satuan = st.text_input(
                        "Satuan",
                        value=var.get("satuan", ""),
                        key=f"satuan_{i}", disabled = is_readonly
                    )
                    var["satuan"] = satuan  # store in session_state
                
                    tipe_data = st.text_area(
                        "Tipe Data",
                        value=var.get("tipe_data", ""),
                        key=f"interpretasi_{i}", disabled = is_readonly
                    )
                    var["tipe_data"] = tipe_data  # store in session_state

                    isian_klasifikasi = st.text_area(
                        "Isian Klasifikasi",
                        value=var.get("isian_klasifikasi", ""),
                        key=f"isian_klasifikasi_{i}", disabled = is_readonly
                    )
                    var["isian_klasifikasi"] = isian_klasifikasi

                    aturan_validasi = st.text_area(
                        "Aturan Validasi",
                        value=var.get("aturan_validasi", ""),
                        key=f"aturan_validasi_{i}", disabled = is_readonly
                    )
                    var["aturan_validasi"] = aturan_validasi

                    kalimat_pertanyaan = st.text_area(
                        "Kalimat Pertanyaan",
                        value=var.get("kalimat_perntanyaan", ""),
                        key=f"kalimat_perntanyaan{i}", disabled = is_readonly
                    )
                    var["kalimat_perntanyaan"] = kalimat_pertanyaan
                    
                    var["dapat_diakses_umum"] = st.checkbox(
                "Variabel Dapat Diakses Umum", value=var.get("dapat_diakses_umum", False), key=f"var_dapat_diakses_umum_{i}", disabled = is_readonly)  
    
    else:
        st.info("Belum ada variabel yang terdeteksi pada MS Kegiatan. Input daftar variabel pada MS Kegiatan BLOK 3")
    
if st.button("💾 Simpan Progres", disabled = is_readonly): 
     
    # ✅ Sync semua section ke form_data dulu
    st.session_state.form_data["halaman_awal"] = st.session_state.get("halaman_awal", {})
    st.session_state.form_data["blok_1_3"] = st.session_state.get("blok_1_3", {})
    st.session_state.form_data["variables"] = st.session_state.get("variables", [])
    st.session_state.form_data["blok_4"] = st.session_state.get("blok_4", {})
    st.session_state.form_data["blok_5"] = st.session_state.get("blok_5", {})
    st.session_state.form_data["blok_6_8"] = st.session_state.get("blok_6_8", {})
    st.session_state.form_data["indicators"] = st.session_state.get("indicators", [])
    
    combined_entry = {
        "activity_id": st.session_state.current_activity_id,
        "owner": username,
        "status": st.session_state.form_data.get("status", "Draft"),
        "last_saved": now_jakarta().strftime("%Y-%m-%d %H:%M:%S"), 
        
        # all sections 
        "halaman_awal": st.session_state.form_data["halaman_awal"],
        "blok_1_3": st.session_state.form_data["blok_1_3"],
        "variables": st.session_state.form_data["variables"],
        "blok_4": st.session_state.form_data["blok_4"],
        "blok_5": st.session_state.form_data["blok_5"],
        "blok_6_8": st.session_state.form_data["blok_6_8"],
        "indicators": st.session_state.form_data["indicators"], 
        
        # metadata 
        "revision_note": st.session_state.form_data.get("revision_note", ""),
        "revision_requested_at": st.session_state.form_data.get("revision_requested_at", ""),
        "rejection_reason": st.session_state.form_data.get("rejection_reason", ""), 
        "verified_by": st.session_state.form_data.get("verified_by", ""),
        "verifier_comment": st.session_state.form_data.get("verifier_comment", "") 
    } 
    success = save_form(
        activity_id=st.session_state.current_activity_id, 
        username=username, 
        data=combined_entry,) 
    
    if success: 
        st.success("✅ Tersimpan!") 
    else: 
        st.error("❌ Gagal menyimpan")


if st.button("📤 Submit", disabled = is_readonly): 
    ok = submit_form(st.session_state.current_activity_id) 
    if ok: 
        st.session_state.form_data["status"] = "Submitted" 
        st.success("🎉 Submitted!") 
        st.rerun() 
    else: 
        st.error("❌ Submit gagal.")

role = st.session_state.get("role", "user")
status = st.session_state.form_data.get("status", "draft")

if role == "verifier":
    st.divider()
    st.subheader("🔍 Verifikasi")

    notes = st.text_area(
                "Komentar",
                value=st.session_state.form_data.get("verifier_comment", "")
            )
    col1, col2, col3 = st.columns (3)
    with col1:
        if st.button("📝 Request Revision"):
            activity_id=st.session_state.current_activity_id
            username=st.session_state["username"]
            data={
                    **st.session_state.form_data,
                    "verifier_comment": notes,
                    # "verified_by": st.session_state["username"],
                    "revision_requested_at": datetime.now().isoformat(),
                    "status": "revision_requested"
                }
            save_form(
                activity_id=activity_id,
                username=username,
                data=data
            )
            upsert_activity(
                    activity_id=activity_id,
                    user_id=username,
                    payload=data,
                    status="revision_requested",
                )
            st.warning(f"📝 Sent back for revision")
            st.rerun()

    with col2:
        if st.button("✅ Accept"):
            activity_id=st.session_state.current_activity_id
            username=st.session_state["username"]
            data={
                    **st.session_state.form_data,
                    # "verifier_comment": notes,
                    "verified_by": st.session_state["username"],
                    "verified_at": datetime.now().isoformat(),
                    "status": "verified"
            }
            save_form(
                activity_id=activity_id,
                username=username,
                data=data
            )
            upsert_activity(
                    activity_id=activity_id,
                    user_id=username,
                    payload=data,
                    status="verified",
                )
            st.warning(f"✅ {judul} verified")
            st.rerun()

    with col3:
        if st.button("❌ Reject"):
            activity_id=st.session_state.current_activity_id
            username=st.session_state["username"]
            data={
                    **st.session_state.form_data,
                    "verifier_comment": notes,
                    # "verified_by": st.session_state["username"],
                    "rejected_at": datetime.now().isoformat(),
                    "status": "rejected"
            }
            save_form(
                activity_id=activity_id,
                username=username,
                data=data
            )
            upsert_activity(
                    activity_id=activity_id,
                    user_id=username,
                    payload=data,
                    status="rejected",
                )
            st.warning(f"❌ Rejected: {judul}")
            st.rerun()
