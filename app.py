import io
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from gspread.exceptions import WorksheetNotFound

st.set_page_config(page_title="İl-İlçe Stok Takip", layout="wide")

TZ = ZoneInfo("Europe/Istanbul")
HAREKET_BASLIKLAR = [
    "id",
    "tarih_saat",
    "islem_turu",
    "lokasyon",
    "urun",
    "ozellik",
    "adet",
    "aciklama",
]

URUN_KATALOGU = {
    "HPV DNA Testi": ["Standart"],
    "Spekulum": ["S", "M", "L"],
    "Kargo Poşeti": ["Standart"],
}

ISTANBUL_ILCELERI = [
    "Adalar",
    "Arnavutköy",
    "Ataşehir",
    "Avcılar",
    "Bağcılar",
    "Bahçelievler",
    "Bakırköy",
    "Başakşehir",
    "Bayrampaşa",
    "Beşiktaş",
    "Beykoz",
    "Beylikdüzü",
    "Beyoğlu",
    "Büyükçekmece",
    "Çatalca",
    "Çekmeköy",
    "Esenler",
    "Esenyurt",
    "Eyüpsultan",
    "Fatih",
    "Gaziosmanpaşa",
    "Güngören",
    "Kadıköy",
    "Kağıthane",
    "Kartal",
    "Küçükçekmece",
    "Maltepe",
    "Pendik",
    "Sancaktepe",
    "Sarıyer",
    "Silivri",
    "Sultanbeyli",
    "Sultangazi",
    "Şile",
    "Şişli",
    "Tuzla",
    "Ümraniye",
    "Üsküdar",
    "Zeytinburnu",
]

ESKI_ORNEK_ILCELER = {"İlçe 1", "İlçe 2", "İlçe 3", "İlçe 4", "İlçe 5"}


@st.cache_resource
def get_spreadsheet():
    creds_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds_dict)
    sheet_url = st.secrets["gsheets"]["spreadsheet_url"]
    return gc.open_by_url(sheet_url)


def get_or_create_worksheet(
    sh, title: str, headers: list[str], default_rows: list[list] | None = None
):
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(len(headers), 5))

    mevcut_basliklar = ws.row_values(1)
    if mevcut_basliklar != headers:
        ws.update(range_name="A1", values=[headers])
        if default_rows:
            ws.append_rows(default_rows, value_input_option="USER_ENTERED")
    return ws


def simdi_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


@st.cache_data(ttl=30)
def verileri_getir() -> tuple[pd.DataFrame, list[str]]:
    sh = get_spreadsheet()
    ws_hareket = get_or_create_worksheet(sh, "hareketler", HAREKET_BASLIKLAR)
    ws_ilce = get_or_create_worksheet(
        sh,
        "ilceler",
        ["ilce_adi"],
        [[ilce] for ilce in ISTANBUL_ILCELERI],
    )

    ham_kayitlar = ws_hareket.get_all_records()
    kayitlar = [k for k in ham_kayitlar if str(k.get("urun", "")).strip()]

    if not kayitlar:
        df = pd.DataFrame(columns=HAREKET_BASLIKLAR)
    else:
        df = pd.DataFrame(kayitlar)
        df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
        df["adet"] = pd.to_numeric(df["adet"], errors="coerce").fillna(0).astype(int)
        for col in ["tarih_saat", "islem_turu", "lokasyon", "urun", "ozellik", "aciklama"]:
            df[col] = df[col].astype(str)
        df = df.sort_values(by="id", ascending=False).reset_index(drop=True)

    ilce_sutunu = [x.strip() for x in ws_ilce.col_values(1)[1:] if x.strip()]

    if not ilce_sutunu or set(ilce_sutunu).issubset(ESKI_ORNEK_ILCELER):
        ws_ilce.clear()
        ws_ilce.update(
            range_name="A1",
            values=[["ilce_adi"]] + [[ilce] for ilce in ISTANBUL_ILCELERI],
        )
        ilceler = ISTANBUL_ILCELERI
    else:
        ilceler = ilce_sutunu

    return df, ilceler


def hareket_ekle(
    islem_turu: str,
    lokasyon: str,
    urun: str,
    ozellik: str,
    adet: int,
    aciklama: str = "",
):
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, "hareketler", HAREKET_BASLIKLAR)
    mevcut_idler = [int(x) for x in ws.col_values(1)[1:] if str(x).isdigit()]
    yeni_id = max(mevcut_idler, default=0) + 1

    yeni_satir = [
        yeni_id,
        simdi_str(),
        islem_turu,
        lokasyon.strip(),
        urun.strip(),
        ozellik.strip(),
        int(adet),
        aciklama.strip(),
    ]
    ws.append_row(yeni_satir, value_input_option="USER_ENTERED")
    st.cache_data.clear()


def anlik_stok_hesapla(df_hareket: pd.DataFrame) -> pd.DataFrame:
    if df_hareket.empty:
        return pd.DataFrame(columns=["Lokasyon", "Ürün", "Özellik", "Mevcut Adet"])

    kayitlar = []
    for _, row in df_hareket.iterrows():
        if row["islem_turu"] == "ANA_DEPO_GIRIS":
            kayitlar.append(
                {
                    "Lokasyon": "İl Ana Depo",
                    "Ürün": row["urun"],
                    "Özellik": row["ozellik"],
                    "Degisim": row["adet"],
                }
            )
        elif row["islem_turu"] == "ILCE_CIKIS":
            kayitlar.append(
                {
                    "Lokasyon": "İl Ana Depo",
                    "Ürün": row["urun"],
                    "Özellik": row["ozellik"],
                    "Degisim": -row["adet"],
                }
            )
            kayitlar.append(
                {
                    "Lokasyon": row["lokasyon"],
                    "Ürün": row["urun"],
                    "Özellik": row["ozellik"],
                    "Degisim": row["adet"],
                }
            )

    if not kayitlar:
        return pd.DataFrame(columns=["Lokasyon", "Ürün", "Özellik", "Mevcut Adet"])

    df_stok = (
        pd.DataFrame(kayitlar)
        .groupby(["Lokasyon", "Ürün", "Özellik"], as_index=False)["Degisim"]
        .sum()
        .rename(columns={"Degisim": "Mevcut Adet"})
    )
    return df_stok.sort_values(by=["Lokasyon", "Ürün", "Özellik"]).reset_index(drop=True)


def excel_olustur(df_stok: pd.DataFrame, df_hareket: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_stok.to_excel(writer, sheet_name="Anlik_Stok", index=False)

        if not df_stok.empty:
            df_pivot = df_stok.pivot_table(
                index=["Ürün", "Özellik"],
                columns="Lokasyon",
                values="Mevcut Adet",
                aggfunc="sum",
                fill_value=0,
            ).reset_index()
            df_pivot.to_excel(writer, sheet_name="Il_Ilce_Matrisi", index=False)

        df_log = df_hareket.rename(
            columns={
                "id": "Kayıt No",
                "tarih_saat": "Tarih ve Saat",
                "islem_turu": "İşlem Türü",
                "lokasyon": "Lokasyon",
                "urun": "Ürün",
                "ozellik": "Özellik",
                "adet": "Adet",
                "aciklama": "Açıklama",
            }
        )
        df_log.to_excel(writer, sheet_name="Hareket_Gecmisi", index=False)

    return output.getvalue()


# --- UYGULAMA ARAYÜZÜ ---
st.title("Stok Takip Sistemi")

try:
    df_hareket, aktif_ilceler = verileri_getir()
except Exception as e:
    st.error(
        "Google Sheets bağlantısı kurulamadı. Secrets ayarlarını ve tablo paylaşım iznini kontrol edin.\n\n"
        f"Detay: {e}"
    )
    st.stop()

df_stok = anlik_stok_hesapla(df_hareket)

col_m1, col_m2, col_m3, col_aksiyon = st.columns([2, 2, 2, 2])
ana_depo_toplam = (
    int(df_stok[df_stok["Lokasyon"] == "İl Ana Depo"]["Mevcut Adet"].sum())
    if not df_stok.empty
    else 0
)
ilce_toplam = (
    int(df_stok[df_stok["Lokasyon"] != "İl Ana Depo"]["Mevcut Adet"].sum())
    if not df_stok.empty
    else 0
)

col_m1.metric("İl Ana Depo Toplam", f"{ana_depo_toplam:,}")
col_m2.metric("İlçeler Toplam", f"{ilce_toplam:,}")
col_m3.metric("Genel Toplam", f"{ana_depo_toplam + ilce_toplam:,}")

with col_aksiyon:
    excel_verisi = excel_olustur(df_stok, df_hareket)
    dosya_adi = f"stok_raporu_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        label="Excel İndir (.xlsx)",
        data=excel_verisi,
        file_name=dosya_adi,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    if st.button("Tabloyu Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

sekme_durum, sekme_giris, sekme_cikis, sekme_gecmis = st.tabs(
    ["Anlık Stok Durumu", "İl Ana Depoya Giriş", "İlçeye Çıkış Yap", "Hareket Geçmişi"]
)

# 1. SEKME: ANLIK STOK
with sekme_durum:
    if df_stok.empty:
        st.info(
            "Henüz stok hareketi bulunmuyor. 'İl Ana Depoya Giriş' sekmesinden ilk kaydı ekleyebilirsiniz."
        )
    else:
        f_col1, f_col2 = st.columns(2)
        lokasyonlar = ["Tümü"] + sorted(df_stok["Lokasyon"].unique().tolist())
        tum_urunler = sorted(
            set(list(URUN_KATALOGU.keys()) + df_stok["Ürün"].unique().tolist())
        )
        urunler = ["Tümü"] + tum_urunler

        secilen_lokasyon = f_col1.selectbox("Lokasyon Filtrele", lokasyonlar)
        secilen_urun = f_col2.selectbox("Ürün Filtrele", urunler)

        df_goster = df_stok.copy()
        if secilen_lokasyon != "Tümü":
            df_goster = df_goster[df_goster["Lokasyon"] == secilen_lokasyon]
        if secilen_urun != "Tümü":
            df_goster = df_goster[df_goster["Ürün"] == secilen_urun]

        st.dataframe(df_goster, use_container_width=True, hide_index=True)

# 2. SEKME: İL ANA DEPOYA GİRİŞ
with sekme_giris:
    st.caption(f"Kayıt zamanı otomatik atanacaktır (Şu an: {simdi_str()})")

    secenek_listesi = list(URUN_KATALOGU.keys()) + ["+ Diğer (Yeni Ürün Ekle)"]
    c_u1, c_u2 = st.columns(2)
    secilen_urun_tipi = c_u1.selectbox("Ürün Seçin", secenek_listesi)

    if secilen_urun_tipi == "+ Diğer (Yeni Ürün Ekle)":
        final_urun = c_u1.text_input("Yeni Ürün Adı")
        final_ozellik = c_u2.text_input(
            "Özellik / Boyut (Boş bırakılırsa Standart kaydedilir)", value="Standart"
        )
    else:
        final_urun = secilen_urun_tipi
        ozellik_listesi = URUN_KATALOGU[secilen_urun_tipi]
        if len(ozellik_listesi) > 1:
            final_ozellik = c_u2.selectbox("Boyut / Özellik Seçin", ozellik_listesi)
        else:
            final_ozellik = ozellik_listesi[0]
            c_u2.text_input("Özellik", value=final_ozellik, disabled=True)

    with st.form("ana_depo_giris_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        giris_adet = c1.number_input("Giriş Adedi", min_value=1, step=1, value=1)
        giris_aciklama = c2.text_input("Açıklama / İrsaliye No (İsteğe bağlı)")

        if st.form_submit_button("Ana Depoya Kaydet", type="primary"):
            temiz_urun = final_urun.strip()
            temiz_ozellik = final_ozellik.strip() if final_ozellik.strip() else "Standart"

            if not temiz_urun:
                st.error("Ürün adı boş bırakılamaz.")
            else:
                with st.spinner("Google Sheets'e kaydediliyor..."):
                    hareket_ekle(
                        "ANA_DEPO_GIRIS",
                        "İl Ana Depo",
                        temiz_urun,
                        temiz_ozellik,
                        giris_adet,
                        giris_aciklama,
                    )
                st.success(
                    f"{temiz_urun} ({temiz_ozellik}) - {giris_adet} adet İl Ana Depoya eklendi."
                )
                st.rerun()

# 3. SEKME: İLÇEYE ÇIKIŞ
with sekme_cikis:
    st.caption(f"Çıkış zamanı otomatik atanacaktır (Şu an: {simdi_str()})")
    ana_depo_stok = df_stok[
        (df_stok["Lokasyon"] == "İl Ana Depo") & (df_stok["Mevcut Adet"] > 0)
    ]

    if ana_depo_stok.empty:
        st.warning("İl Ana Depoda sevk edilebilecek mevcut stok bulunmuyor.")
    else:
        ana_depo_stok = ana_depo_stok.copy()
        ana_depo_stok["Etiket"] = (
            ana_depo_stok["Ürün"]
            + " | "
            + ana_depo_stok["Özellik"]
            + " (Mevcut: "
            + ana_depo_stok["Mevcut Adet"].astype(str)
            + ")"
        )

        with st.form("ilce_cikis_form", clear_on_submit=True):
            secilen_etiket = st.selectbox(
                "Ana Depodan Çıkılacak Ürün ve Özellik", ana_depo_stok["Etiket"].tolist()
            )
            secilen_satir = ana_depo_stok[ana_depo_stok["Etiket"] == secilen_etiket].iloc[0]
            maks_adet = int(secilen_satir["Mevcut Adet"])

            c1, c2 = st.columns(2)
            hedef_ilce = c1.selectbox("Hedef İlçe", aktif_ilceler)
            cikis_adet = c2.number_input(
                "Çıkış Adedi", min_value=1, max_value=maks_adet, step=1, value=1
            )
            cikis_aciklama = st.text_input("Açıklama / Teslim Alan (İsteğe bağlı)")

            if st.form_submit_button("İlçeye Çıkışı Onayla", type="primary"):
                with st.spinner("Google Sheets güncelleniyor..."):
                    hareket_ekle(
                        "ILCE_CIKIS",
                        hedef_ilce,
                        secilen_satir["Ürün"],
                        secilen_satir["Özellik"],
                        cikis_adet,
                        cikis_aciklama,
                    )
                st.success(
                    f"{secilen_satir['Ürün']} ({secilen_satir['Özellik']}) - {cikis_adet} adet {hedef_ilce} stoğuna aktarıldı."
                )
                st.rerun()

# 4. SEKME: HAREKET GEÇMİŞİ
with sekme_gecmis:
    if df_hareket.empty:
        st.info("Henüz işlem kaydı yok.")
    else:
        df_goster_log = df_hareket.copy()
        df_goster_log["islem_turu"] = df_goster_log["islem_turu"].map(
            {"ANA_DEPO_GIRIS": "İl Ana Depo Giriş", "ILCE_CIKIS": "İlçeye Çıkış"}
        )
        st.dataframe(
            df_goster_log.rename(
                columns={
                    "id": "No",
                    "tarih_saat": "Tarih ve Saat",
                    "islem_turu": "İşlem",
                    "lokasyon": "Lokasyon",
                    "urun": "Ürün",
                    "ozellik": "Özellik",
                    "adet": "Adet",
                    "aciklama": "Açıklama",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
