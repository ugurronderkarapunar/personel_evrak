import hashlib
import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import db
from pdf_parser import extract_text, parse_document

st.set_page_config(page_title="Belge Takip", page_icon="🚢", layout="wide")
TODAY = datetime.now(ZoneInfo("Europe/Istanbul")).date()


def login():
    if st.session_state.get("ok"):
        return
    st.title("🚢 Belge Takip")
    pw = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        if hmac.compare_digest(pw, st.secrets["APP_PASSWORD"]):
            st.session_state.ok = True
            st.rerun()
        st.error("Şifre hatalı.")
    st.stop()


@st.cache_resource
def setup():
    db.init_db()
    return True


login()
setup()
people = db.query("SELECT * FROM personel ORDER BY soyad, ad")
st.title("🚢 Belge Takip")
tab_up, tab_list, tab_ppl = st.tabs(["📄 Belge Yükle", "📋 Belgeler", "👤 Personel"])

# ---------------- Personel ----------------
with tab_ppl:
    with st.form("yeni_personel", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        ad = c1.text_input("Ad")
        soyad = c2.text_input("Soyad")
        unvan = c3.text_input("Ünvan")
        if st.form_submit_button("Personel Ekle"):
            if ad.strip() and soyad.strip() and unvan.strip():
                db.execute("INSERT INTO personel (ad, soyad, unvan) VALUES (%s,%s,%s)",
                           (ad.strip(), soyad.strip(), unvan.strip()))
                st.rerun()
            else:
                st.warning("Üç alan da dolu olmalı.")
    if people:
        st.dataframe(pd.DataFrame(people)[["id", "ad", "soyad", "unvan"]],
                     hide_index=True, use_container_width=True)
        with st.expander("Personel sil (belgeleri de silinir)"):
            sil = st.selectbox("Personel", [p["id"] for p in people],
                               format_func=lambda i: next(
                                   f'{p["ad"]} {p["soyad"]}' for p in people if p["id"] == i),
                               key="sil_p")
            if st.button("Sil", key="sil_p_btn"):
                db.execute("DELETE FROM personel WHERE id=%s", (sil,))
                st.rerun()

# ---------------- Belge yükle ----------------
with tab_up:
    if not people:
        st.info("Önce 'Personel' sekmesinden personel ekle.")
    else:
        up = st.file_uploader("PDF veya fotoğraf yükle", type=["pdf", "png", "jpg", "jpeg"])
        if up:
            data = up.getvalue()
            key = hashlib.md5(data).hexdigest()[:10]
            if st.session_state.get("parse_key") != key:
                with st.spinner("Okunuyor..."):
                    text, mode, info = extract_text(data, up.name.lower().endswith(".pdf"))
                st.session_state.update(parse_key=key, text=text, mode=mode, info=info,
                                        parsed=parse_document(text, people))
            res, text, mode = st.session_state.parsed, st.session_state.text, st.session_state.mode
            st.caption(f"Okuma yöntemi: {'doğrudan metin' if mode == 'metin' else 'OCR (tarama)'}")
            if not (res["start"] and res["end"]):
                st.warning("Tarihlerin tamamı bulunamadı, lütfen kontrol edip düzelt.")
            if not text.strip():
                st.error("Dosyadan hiç metin okunamadı.")
            with st.expander("Tanı bilgisi"):
                st.write(st.session_state.get("info", []))

            ids = [p["id"] for p in people]
            idx = ids.index(res["person_id"]) if res["person_id"] in ids else 0
            pid = st.selectbox("Personel", ids, index=idx, key=f"p_{key}",
                               format_func=lambda i: next(
                                   f'{p["ad"]} {p["soyad"]} – {p["unvan"]}'
                                   for p in people if p["id"] == i))
            belge = st.text_input("Belge adı", res["doc_name"], key=f"n_{key}")
            c1, c2 = st.columns(2)
            bas = c1.date_input("Başlangıç", res["start"] or TODAY,
                                format="DD.MM.YYYY", key=f"s_{key}")
            bit = c2.date_input("Bitiş", res["end"] or TODAY,
                                format="DD.MM.YYYY", key=f"e_{key}")
            with st.expander("Okunan ham metin"):
                st.text(text[:3000])
            if st.button("💾 Kaydet", type="primary", key=f"k_{key}"):
                if not belge.strip():
                    st.error("Belge adı boş olamaz.")
                elif bit < bas:
                    st.error("Bitiş tarihi başlangıçtan önce olamaz.")
                else:
                    n = db.execute(
                        """INSERT INTO belge (personel_id, belge_adi, baslangic, bitis, dosya_adi)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (pid, belge.strip(), bas, bit, up.name))
                    st.success("Kaydedildi.") if n else st.info("Bu belge zaten kayıtlı.")

# ---------------- Liste ----------------
with tab_list:
    rows = db.query("""SELECT b.id, p.ad, p.soyad, p.unvan, b.belge_adi, b.baslangic, b.bitis
                       FROM belge b JOIN personel p ON p.id=b.personel_id ORDER BY b.bitis""")
    if not rows:
        st.info("Henüz belge yok.")
    else:
        df = pd.DataFrame(rows)
        df["kalan_gun"] = df["bitis"].apply(lambda d: (d - TODAY).days)
        df["durum"] = df["kalan_gun"].apply(
            lambda k: "🔴 SÜRESİ DOLDU" if k < 0 else ("🟠 15 GÜN İÇİNDE" if k <= 15 else "🟢 Geçerli"))
        m1, m2 = st.columns(2)
        m1.metric("Süresi dolan", int((df.kalan_gun < 0).sum()))
        m2.metric("15 gün içinde dolacak", int(df.kalan_gun.between(0, 15).sum()))
        f = st.selectbox("Filtre", ["Hepsi", "🔴 SÜRESİ DOLDU", "🟠 15 GÜN İÇİNDE", "🟢 Geçerli"])
        if f != "Hepsi":
            df = df[df.durum == f]
        show = df.copy()
        for c in ("baslangic", "bitis"):
            show[c] = pd.to_datetime(show[c]).dt.strftime("%d.%m.%Y")
        st.dataframe(show.rename(columns={
            "ad": "Ad", "soyad": "Soyad", "unvan": "Ünvan", "belge_adi": "Belge",
            "baslangic": "Başlangıç", "bitis": "Bitiş", "kalan_gun": "Kalan Gün",
            "durum": "Durum"}), hide_index=True, use_container_width=True)
        with st.expander("Belge sil"):
            sid = st.selectbox("Belge", df["id"].tolist(), key="sil_b",
                               format_func=lambda i: "{} {} – {}".format(
                                   *df[df.id == i][["ad", "soyad", "belge_adi"]].iloc[0]))
            if st.button("Sil", key="sil_b_btn"):
                db.execute("DELETE FROM belge WHERE id=%s", (sid,))
                st.rerun()
