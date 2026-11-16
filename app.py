import html
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from gspread.exceptions import WorksheetNotFound

st.set_page_config(page_title="Stok Takip", page_icon="📦", layout="wide")

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

ISLEM_ETIKETLERI = {
    "ANA_DEPO_GIRIS": "İl Ana Depo Giriş",
    "ILCE_CIKIS": "İlçeye Çıkış",
    "ILCE_KULLANIM": "İlçe Kullanım",
    "ILCE_ZAYI": "İlçe Zayi",
}

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


def render_html(raw_html: str):
    temiz = "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())
    st.markdown(temiz, unsafe_allow_html=True)


def urun_gorsel_bilgisi(urun_adi: str, boyut: int = 24) -> dict:
    ad = urun_adi.strip().lower()

    if "hpv" in ad or "test" in ad:
        return {
            "renk": "#4F46E5",
            "bg": "rgba(79, 70, 229, 0.12)",
            "svg": (
                f'<svg width="{boyut}" height="{boyut}" viewBox="0 0 24 24" fill="none" '
                'stroke="#4F46E5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M9 3h6"/>'
                '<path d="M10 3v14a2 2 0 0 0 4 0V3"/>'
                '<path d="M10 10h4"/>'
                '<circle cx="12" cy="14" r="1" fill="#4F46E5"/>'
                "</svg>"
            ),
        }
    if "spekulum" in ad:
        return {
            "renk": "#0D9488",
            "bg": "rgba(13, 148, 136, 0.12)",
            "svg": (
                f'<svg width="{boyut}" height="{boyut}" viewBox="0 0 24 24" fill="none" '
                'stroke="#0D9488" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M4 8l13-3c1.5-.3 3 .8 3 2.3 0 1.1-.8 2.1-1.9 2.3L7 12"/>'
                '<path d="M4 13l13 2c1.5.2 2.5 1.5 2.2 3-.2 1.1-1.2 1.9-2.3 1.8L6 17"/>'
                '<path d="M7 12v8a1 1 0 0 1-2 0v-7"/>'
                "</svg>"
            ),
        }
    if "kargo" in ad or "poşet" in ad or "poset" in ad:
        return {
            "renk": "#D97706",
            "bg": "rgba(217, 119, 6, 0.12)",
            "svg": (
                f'<svg width="{boyut}" height="{boyut}" viewBox="0 0 24 24" fill="none" '
                'stroke="#D97706" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M5 4h14a1 1 0 0 1 1 1v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z"/>'
                '<path d="M4 8h16"/>'
                '<path d="M9 13h6"/>'
                '<path d="M9 16h4"/>'
                "</svg>"
            ),
        }
    return {
        "renk": "#475569",
        "bg": "rgba(71, 85, 105, 0.12)",
        "svg": (
            f'<svg width="{boyut}" height="{boyut}" viewBox="0 0 24 24" fill="none" '
            'stroke="#475569" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>'
            '<path d="m3.3 7 8.7 5 8.7-5"/>'
            '<path d="M12 22V12"/>'
            "</svg>"
        ),
    }


def stil_uygula():
    render_html(
        """
        <style>
        .prod-icon-wrap {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .legend-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 12px;
        }
        .legend-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 10px;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: 600;
        }
        .legend-icon {
            width: 28px;
            height: 28px;
            border-radius: 7px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .preview-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 10px;
            padding: 10px 14px;
            margin: 6px 0 12px 0;
        }
        .preview-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .preview-badge {
            font-size: 12.5px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 8px;
            background: rgba(128, 128, 128, 0.12);
        }
        .cart-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 6px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 9px 14px;
            font-weight: 600;
        }
        </style>
        """
    )


def urun_onizleme_karti_goster(urun_adi: str, ozellik: str, stok_bilgisi: str):
    gorsel = urun_gorsel_bilgisi(urun_adi, boyut=22)
    guvenli_urun = html.escape(urun_adi.strip() or "Yeni Ürün")
    guvenli_ozellik = html.escape(ozellik.strip() or "Standart")
    guvenli_stok = html.escape(stok_bilgisi)

    render_html(
        f"""
        <div class="preview-banner">
            <div class="preview-left">
                <div class="prod-icon-wrap" style="background: {gorsel['bg']};">
                    {gorsel['svg']}
                </div>
                <div>
                    <div style="font-weight: 600; font-size: 14.5px;">{guvenli_urun}</div>
                    <div style="font-size: 12px; opacity: 0.78;">Özellik / Boyut: <strong>{guvenli_ozellik}</strong></div>
                </div>
            </div>
            <div class="preview-badge">{guvenli_stok}</div>
        </div>
        """
    )


def stok_urun_seridi_goster():
    etiketler = []
    for urun_adi, ozellikler in URUN_KATALOGU.items():
        gorsel = urun_gorsel_bilgisi(urun_adi, boyut=18)
        alt_bilgi = f" ({'-'.join(ozellikler)})" if len(ozellikler) > 1 else ""
        etiketler.append(
            f"""
            <div class="legend-chip">
                <span class="legend-icon" style="background: {gorsel['bg']};">{gorsel['svg']}</span>
                <span>{html.escape(urun_adi)}{html.escape(alt_bilgi)}</span>
            </div>
            """
        )
    render_html(f'<div class="legend-strip">{"".join(etiketler)}</div>')


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
) -> tuple[int, str]:
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, "hareketler", HAREKET_BASLIKLAR)
    mevcut_idler = [int(x) for x in ws.col_values(1)[1:] if str(x).isdigit()]
    yeni_id = max(mevcut_idler, default=0) + 1
    kayit_zamani = simdi_str()

    yeni_satir = [
        yeni_id,
        kayit_zamani,
        islem_turu,
        lokasyon.strip(),
        urun.strip(),
        ozellik.strip(),
        int(adet),
        aciklama.strip(),
    ]
    ws.append_row(yeni_satir, value_input_option="USER_ENTERED")
    st.cache_data.clear()
    return yeni_id, kayit_zamani


def toplu_ilce_cikis_ekle(
    lokasyon: str,
    kalemler: list[dict],
    aciklama: str = "",
) -> tuple[list[int], str]:
    sh = get_spreadsheet()
    ws = get_or_create_worksheet(sh, "hareketler", HAREKET_BASLIKLAR)
    mevcut_idler = [int(x) for x in ws.col_values(1)[1:] if str(x).isdigit()]
    baslangic_id = max(mevcut_idler, default=0) + 1
    kayit_zamani = simdi_str()

    eklenen_idler = []
    satirlar = []
    for idx, kalem in enumerate(kalemler):
        kayit_id = baslangic_id + idx
        eklenen_idler.append(kayit_id)
        satirlar.append(
            [
                kayit_id,
                kayit_zamani,
                "ILCE_CIKIS",
                lokasyon.strip(),
                kalem["urun"].strip(),
                kalem["ozellik"].strip(),
                int(kalem["adet"]),
                aciklama.strip(),
            ]
        )

    ws.append_rows(satirlar, value_input_option="USER_ENTERED")
    st.cache_data.clear()
    return eklenen_idler, kayit_zamani


def anlik_stok_hesapla(df_hareket: pd.DataFrame) -> pd.DataFrame:
    if df_hareket.empty:
        return pd.DataFrame(columns=["Lokasyon", "Ürün", "Özellik", "Mevcut Adet"])

    kayitlar = []
    for _, row in df_hareket.iterrows():
        tur = row["islem_turu"]
        if tur == "ANA_DEPO_GIRIS":
            kayitlar.append(
                {
                    "Lokasyon": "İl Ana Depo",
                    "Ürün": row["urun"],
                    "Özellik": row["ozellik"],
                    "Degisim": row["adet"],
                }
            )
        elif tur == "ILCE_CIKIS":
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
        elif tur in ("ILCE_KULLANIM", "ILCE_ZAYI"):
            kayitlar.append(
                {
                    "Lokasyon": row["lokasyon"],
                    "Ürün": row["urun"],
                    "Özellik": row["ozellik"],
                    "Degisim": -row["adet"],
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


def sade_stok_ozeti_olustur(df_stok: pd.DataFrame) -> pd.DataFrame:
    """İl Ana Depo ve ilçelerin elindeki mevcut stokları sade bir özet tablo haline getirir."""
    temel_sutunlar = [
        "HPV DNA Testi",
        "Spekulum (S)",
        "Spekulum (M)",
        "Spekulum (L)",
        "Kargo Poşeti",
    ]

    if df_stok.empty:
        return pd.DataFrame(columns=["Lokasyon"] + temel_sutunlar)

    df_temp = df_stok.copy()
    df_temp["Kalem"] = df_temp.apply(
        lambda r: r["Ürün"]
        if str(r["Özellik"]).strip() in ("", "Standart")
        else f"{r['Ürün']} ({r['Özellik']})",
        axis=1,
    )

    pivot = df_temp.pivot_table(
        index="Lokasyon",
        columns="Kalem",
        values="Mevcut Adet",
        aggfunc="sum",
        fill_value=0,
    )

    for col in temel_sutunlar:
        if col not in pivot.columns:
            pivot[col] = 0

    ekstra_sutunlar = [c for c in pivot.columns if c not in temel_sutunlar]
    sirali_sutunlar = temel_sutunlar + ekstra_sutunlar
    pivot = pivot[sirali_sutunlar]

    diger_lokasyonlar = sorted([lok for lok in pivot.index if lok != "İl Ana Depo"])
    if "İl Ana Depo" in pivot.index:
        sirali_indeks = ["İl Ana Depo"] + diger_lokasyonlar
    else:
        sirali_indeks = diger_lokasyonlar

    pivot = pivot.reindex(sirali_indeks).reset_index()
    return pivot


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

        if not df_hareket.empty:
            df_sarf = df_hareket[
                df_hareket["islem_turu"].isin(["ILCE_KULLANIM", "ILCE_ZAYI"])
            ].copy()
            if not df_sarf.empty:
                df_sarf["Tur_Adi"] = df_sarf["islem_turu"].map(
                    {"ILCE_KULLANIM": "Kullanılan Adet", "ILCE_ZAYI": "Zayi Adet"}
                )
                df_sarf_ozet = df_sarf.pivot_table(
                    index=["lokasyon", "urun", "ozellik"],
                    columns="Tur_Adi",
                    values="adet",
                    aggfunc="sum",
                    fill_value=0,
                ).reset_index()
                df_sarf_ozet = df_sarf_ozet.rename(
                    columns={"lokasyon": "İlçe", "urun": "Ürün", "ozellik": "Özellik"}
                )
                df_sarf_ozet.to_excel(writer, sheet_name="Ilce_Kullanim_Zayi", index=False)

        df_log = df_hareket.copy()
        if not df_log.empty:
            df_log["islem_turu"] = df_log["islem_turu"].map(
                lambda x: ISLEM_ETIKETLERI.get(x, x)
            )
        df_log = df_log.rename(
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


def tutanak_html_olustur(veri: dict) -> str:
    kayit_no = html.escape(str(veri.get("kayit_no", "-")))
    tarih_saat = html.escape(str(veri.get("tarih_saat", "-")))
    islem_turu = veri.get("islem_turu", "")
    lokasyon = html.escape(str(veri.get("lokasyon", "-")))
    aciklama = html.escape(str(veri.get("aciklama", "")).strip() or "-")

    kalemler = veri.get("kalemler")
    if not kalemler:
        kalemler = [
            {
                "urun": veri.get("urun", "-"),
                "ozellik": veri.get("ozellik", "-"),
                "adet": veri.get("adet", 0),
            }
        ]

    satirlar_html = []
    spekulum_kalemleri = []

    for idx, k in enumerate(kalemler, start=1):
        u_ham = str(k.get("urun", "-"))
        u_esc = html.escape(u_ham)
        oz_esc = html.escape(str(k.get("ozellik", "-")))
        ad_int = int(k.get("adet", 0))

        if u_ham.strip().lower() == "spekulum":
            spekulum_kalemleri.append(k)

        u_svg = urun_gorsel_bilgisi(u_ham, boyut=18)["svg"]
        satirlar_html.append(
            f"""
            <tr>
              <td>{idx}</td>
              <td><div class="item-cell-flex">{u_svg}<strong>{u_esc}</strong></div></td>
              <td>{oz_esc}</td>
              <td><strong>{ad_int:,} Adet</strong></td>
            </tr>
            """
        )

    if len(spekulum_kalemleri) > 1:
        spekulum_toplam = sum(int(x.get("adet", 0)) for x in spekulum_kalemleri)
        beden_sirasi = {"S": 0, "M": 1, "L": 2}
        beden_etiket = "-".join(
            sorted(
                {str(x.get("ozellik", "")).strip() for x in spekulum_kalemleri},
                key=lambda b: beden_sirasi.get(b, 99),
            )
        )
        satirlar_html.append(
            f"""
            <tr style="background: #f2f4f7;">
              <td colspan="3" style="text-align: right;"><strong>Spekulum Toplamı ({html.escape(beden_etiket)}):</strong></td>
              <td><strong>{spekulum_toplam:,} Adet</strong></td>
            </tr>
            """
        )

    if islem_turu == "ANA_DEPO_GIRIS":
        ust_baslik = "MALZEME TESLİM - TESELLÜM TUTANAĞI"
        islem_baslik = "İL ANA DEPO GİRİŞ TUTANAĞI"
        gonderen_birim = "Tedarikçi / Gönderen Birim"
        alan_birim = "İstanbul İl Ana Depo"
        sol_imza_baslik = "TESLİM EDEN"
        sag_imza_baslik = "TESLİM ALAN"
        beyan_metni = (
            "Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler eksiksiz ve sağlam "
            "olarak İl Ana Depo stoklarına teslim alınmıştır."
        )
    elif islem_turu == "ILCE_KULLANIM":
        ust_baslik = "MALZEME SARF / KULLANIM BİLDİRİM TUTANAĞI"
        islem_baslik = f"{lokasyon.upper()} İLÇE SAHA KULLANIM TUTANAĞI"
        gonderen_birim = f"{lokasyon} İlçe Birimi"
        alan_birim = "Saha Tarama / Hizmet Kullanımı"
        sol_imza_baslik = "BİLDİRİMİ YAPAN"
        sag_imza_baslik = "BİRİM SORUMLUSU / ONAY"
        beyan_metni = (
            f"Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler {lokasyon} İlçe Birimi "
            f"tarafından yürütülen saha ve tarama faaliyetlerinde kullanılmış olup ilçe stoğundan düşülmüştür."
        )
    elif islem_turu == "ILCE_ZAYI":
        ust_baslik = "MALZEME ZAYİ / İMHA TESPİT TUTANAĞI"
        islem_baslik = f"{lokasyon.upper()} İLÇE ZAYİ BİLDİRİM TUTANAĞI"
        gonderen_birim = f"{lokasyon} İlçe Birimi"
        alan_birim = "Zayi / Kullanım Dışı Stok Düşümü"
        sol_imza_baslik = "TESPİT EDEN"
        sag_imza_baslik = "BİRİM SORUMLUSU / ONAY"
        beyan_metni = (
            f"Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler {lokasyon} İlçe Birimi "
            f"kayıtlarında belirtilen gerekçeyle zayi/kullanım dışı olarak tespit edilmiş ve ilçe stoğundan düşülmüştür."
        )
    else:
        ust_baslik = "MALZEME TESLİM - TESELLÜM TUTANAĞI"
        islem_baslik = "İLÇE MALZEME SEVK VE TESLİM TUTANAĞI"
        gonderen_birim = "İstanbul İl Ana Depo"
        alan_birim = f"{lokasyon} İlçe Birimi"
        sol_imza_baslik = "TESLİM EDEN"
        sag_imza_baslik = "TESLİM ALAN"
        beyan_metni = (
            f"Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler İl Ana Depodan çıkış "
            f"yapılarak {alan_birim} yetkilisine eksiksiz ve sağlam olarak teslim edilmiştir."
        )

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Tutanak - No {kayit_no}</title>
<style>
  body {{
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    color: #111;
    background: #f4f6f8;
    margin: 0;
    padding: 16px;
  }}
  .toolbar {{
    max-width: 780px;
    margin: 0 auto 14px auto;
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }}
  .print-btn {{
    background: #1f6feb;
    color: #fff;
    border: none;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    border-radius: 6px;
    cursor: pointer;
  }}
  .print-btn:hover {{
    background: #1859bd;
  }}
  .page {{
    max-width: 780px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #cfd6de;
    padding: 36px 42px;
    box-sizing: border-box;
  }}
  .header {{
    text-align: center;
    border-bottom: 2px solid #111;
    padding-bottom: 14px;
    margin-bottom: 20px;
  }}
  .header h1 {{
    font-size: 18px;
    margin: 0 0 6px 0;
    letter-spacing: 0.4px;
  }}
  .header h2 {{
    font-size: 14px;
    font-weight: 600;
    margin: 0;
    color: #333;
  }}
  .meta-table, .item-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    font-size: 13.5px;
  }}
  .meta-table td {{
    border: 1px solid #333;
    padding: 8px 10px;
  }}
  .meta-label {{
    font-weight: 600;
    background: #f2f4f7;
    width: 24%;
  }}
  .item-table th {{
    border: 1px solid #333;
    background: #f2f4f7;
    padding: 9px 10px;
    text-align: left;
    font-weight: 600;
  }}
  .item-table td {{
    border: 1px solid #333;
    padding: 9px 10px;
  }}
  .item-cell-flex {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .note-box {{
    border: 1px solid #333;
    padding: 10px 12px;
    font-size: 13px;
    margin-bottom: 22px;
    background: #fafafa;
  }}
  .declaration {{
    font-size: 13.5px;
    line-height: 1.55;
    margin-bottom: 34px;
  }}
  .signatures {{
    display: flex;
    justify-content: space-between;
    gap: 32px;
    margin-top: 20px;
  }}
  .sig-box {{
    width: 48%;
    border: 1px solid #333;
    padding: 14px 16px;
    min-height: 145px;
    box-sizing: border-box;
  }}
  .sig-title {{
    text-align: center;
    font-weight: 700;
    font-size: 14px;
    border-bottom: 1px solid #999;
    padding-bottom: 6px;
    margin-bottom: 14px;
  }}
  .sig-line {{
    font-size: 13px;
    margin-bottom: 10px;
  }}
  @media print {{
    @page {{
      size: A4 portrait;
      margin: 16mm;
    }}
    body {{
      background: #fff;
      padding: 0;
    }}
    .toolbar {{
      display: none !important;
    }}
    .page {{
      border: none;
      padding: 0;
      max-width: 100%;
    }}
  }}
</style>
</head>
<body>
  <div class="toolbar">
    <button class="print-btn" onclick="window.print()">Tutanağı Yazdır / PDF Kaydet</button>
  </div>
  <div class="page">
    <div class="header">
      <h1>{ust_baslik}</h1>
      <h2>{islem_baslik}</h2>
    </div>

    <table class="meta-table">
      <tr>
        <td class="meta-label">Tutanak / Kayıt No</td>
        <td>#{kayit_no}</td>
        <td class="meta-label">Tarih ve Saat</td>
        <td>{tarih_saat}</td>
      </tr>
      <tr>
        <td class="meta-label">Çıkış / Kaynak Birim</td>
        <td>{gonderen_birim}</td>
        <td class="meta-label">Hedef / İşlem Türü</td>
        <td>{alan_birim}</td>
      </tr>
    </table>

    <table class="item-table">
      <thead>
        <tr>
          <th style="width: 8%;">Sıra</th>
          <th style="width: 42%;">Ürün Adı</th>
          <th style="width: 30%;">Özellik / Boyut</th>
          <th style="width: 20%;">Miktar (Adet)</th>
        </tr>
      </thead>
      <tbody>
        {"".join(satirlar_html)}
      </tbody>
    </table>

    <div class="note-box">
      <strong>Açıklama / Gerekçe Bilgisi:</strong> {aciklama}
    </div>

    <div class="declaration">
      {beyan_metni} İşbu tutanak 2 (iki) nüsha olarak düzenlenmiş ve taraflarca imza altına alınmıştır.
    </div>

    <div class="signatures">
      <div class="sig-box">
        <div class="sig-title">{sol_imza_baslik}</div>
        <div class="sig-line"><strong>Adı Soyadı:</strong> ..........................................</div>
        <div class="sig-line"><strong>Unvanı:</strong> ...............................................</div>
        <div class="sig-line"><strong>Tarih:</strong> {tarih_saat.split(' ')[0]}</div>
        <div class="sig-line" style="margin-top: 22px;"><strong>İmza:</strong></div>
      </div>
      <div class="sig-box">
        <div class="sig-title">{sag_imza_baslik}</div>
        <div class="sig-line"><strong>Adı Soyadı:</strong> ..........................................</div>
        <div class="sig-line"><strong>Unvanı:</strong> ...............................................</div>
        <div class="sig-line"><strong>Tarih:</strong> {tarih_saat.split(' ')[0]}</div>
        <div class="sig-line" style="margin-top: 22px;"><strong>İmza:</strong></div>
      </div>
    </div>
  </div>
</body>
</html>"""


def tutanak_paneli_goster(tutanak_verisi: dict, session_key: str | None = None):
    html_kod = tutanak_html_olustur(tutanak_verisi)
    st.divider()
    ust_c1, ust_c2, ust_c3 = st.columns([4, 2, 1])
    ust_c1.subheader(f"📄 Tutanak (Kayıt #{tutanak_verisi['kayit_no']})")
    guvenli_dosya_no = str(tutanak_verisi["kayit_no"]).replace(" ", "_").replace(",", "-")
    ust_c2.download_button(
        label="⬇️ Tutanağı İndir",
        data=html_kod.encode("utf-8"),
        file_name=f"tutanak_no_{guvenli_dosya_no}.html",
        mime="text/html",
        use_container_width=True,
        key=f"dl_{session_key}_{guvenli_dosya_no}",
    )
    if session_key and ust_c3.button("✖ Kapat", use_container_width=True, key=f"close_{session_key}"):
        del st.session_state[session_key]
        st.rerun()

    kalem_sayisi = len(tutanak_verisi.get("kalemler") or [1])
    dinamik_yukseklik = 660 + max(0, (kalem_sayisi - 1) * 42)
    components.html(html_kod, height=dinamik_yukseklik, scrolling=True)


# --- UYGULAMA ARAYÜZÜ ---
stil_uygula()

if "cikis_sepeti" not in st.session_state:
    st.session_state["cikis_sepeti"] = []

try:
    df_hareket, aktif_ilceler = verileri_getir()
except Exception as e:
    st.error(
        "Google Sheets bağlantısı kurulamadı. Secrets ayarlarını ve tablo paylaşım iznini kontrol edin.\n\n"
        f"Detay: {e}"
    )
    st.stop()

df_stok = anlik_stok_hesapla(df_hareket)
excel_verisi = excel_olustur(df_stok, df_hareket)
dosya_adi = f"stok_raporu_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}.xlsx"

col_baslik, col_excel, col_yenile = st.columns([6, 2, 1.5])
col_baslik.title("📦 Stok Takip Sistemi")

with col_excel:
    st.write("")
    st.download_button(
        label="📊 Excel İndir",
        data=excel_verisi,
        file_name=dosya_adi,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="ust_excel_indir",
    )

with col_yenile:
    st.write("")
    if st.button("🔄 Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

sekme_durum, sekme_giris, sekme_cikis, sekme_sarf, sekme_gecmis = st.tabs(
    [
        "📊 Stok Durumu",
        "📥 Ana Depo Giriş",
        "📤 İlçeye Çıkış",
        "🩺 Sarf / Zayi",
        "📋 Geçmiş",
    ]
)

# 1. SEKME: SADE STOK DURUMU (İL ANA DEPO VE İLÇELER)
with sekme_durum:
    stok_urun_seridi_goster()

    if df_stok.empty:
        st.info("Henüz stok hareketi bulunmuyor.")
    else:
        df_ozet = sade_stok_ozeti_olustur(df_stok)
        st.dataframe(df_ozet, use_container_width=True, hide_index=True)

        st.download_button(
            label="📥 Ayrıntılı Excel Raporu İndir (.xlsx)",
            data=excel_verisi,
            file_name=dosya_adi,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sekme_excel_indir",
        )

# 2. SEKME: İL ANA DEPOYA GİRİŞ
with sekme_giris:
    secenek_listesi = list(URUN_KATALOGU.keys()) + ["+ Yeni Ürün"]
    c_u1, c_u2 = st.columns(2)
    secilen_urun_tipi = c_u1.selectbox("Ürün", secenek_listesi)

    if secilen_urun_tipi == "+ Yeni Ürün":
        final_urun = c_u1.text_input("Yeni Ürün Adı")
        final_ozellik = c_u2.text_input("Özellik / Boyut", value="Standart")
    else:
        final_urun = secilen_urun_tipi
        ozellik_listesi = URUN_KATALOGU[secilen_urun_tipi]
        if len(ozellik_listesi) > 1:
            final_ozellik = c_u2.selectbox("Boyut", ozellik_listesi)
        else:
            final_ozellik = ozellik_listesi[0]
            c_u2.text_input("Özellik", value=final_ozellik, disabled=True)

    temiz_onizleme_urun = final_urun.strip() or "Yeni Ürün"
    temiz_onizleme_ozellik = final_ozellik.strip() or "Standart"
    mevcut_ana_stok = (
        int(
            df_stok[
                (df_stok["Lokasyon"] == "İl Ana Depo")
                & (df_stok["Ürün"] == temiz_onizleme_urun)
                & (df_stok["Özellik"] == temiz_onizleme_ozellik)
            ]["Mevcut Adet"].sum()
        )
        if not df_stok.empty
        else 0
    )
    urun_onizleme_karti_goster(
        temiz_onizleme_urun,
        temiz_onizleme_ozellik,
        f"Ana Depo Mevcut: {mevcut_ana_stok:,}",
    )

    with st.form("ana_depo_giris_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        giris_adet = c1.number_input("Adet", min_value=1, step=1, value=1)
        giris_aciklama = c2.text_input("Açıklama / İrsaliye No (İsteğe bağlı)")

        if st.form_submit_button("Kaydet ve Tutanak Oluştur", type="primary"):
            temiz_urun = final_urun.strip()
            temiz_ozellik = final_ozellik.strip() if final_ozellik.strip() else "Standart"

            if not temiz_urun:
                st.error("Ürün adı boş bırakılamaz.")
            else:
                with st.spinner("Kaydediliyor..."):
                    yeni_id, kayit_zamani = hareket_ekle(
                        "ANA_DEPO_GIRIS",
                        "İl Ana Depo",
                        temiz_urun,
                        temiz_ozellik,
                        giris_adet,
                        giris_aciklama,
                    )
                st.session_state["son_giris_tutanak"] = {
                    "kayit_no": yeni_id,
                    "tarih_saat": kayit_zamani,
                    "islem_turu": "ANA_DEPO_GIRIS",
                    "lokasyon": "İl Ana Depo",
                    "kalemler": [
                        {
                            "urun": temiz_urun,
                            "ozellik": temiz_ozellik,
                            "adet": giris_adet,
                        }
                    ],
                    "aciklama": giris_aciklama,
                }
                st.success(f"{temiz_urun} ({temiz_ozellik}) - {giris_adet} adet eklendi.")
                st.rerun()

    if "son_giris_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_giris_tutanak"], "son_giris_tutanak")

# 3. SEKME: İLÇEYE ÇIKIŞ
with sekme_cikis:
    ana_depo_stok = df_stok[
        (df_stok["Lokasyon"] == "İl Ana Depo") & (df_stok["Mevcut Adet"] > 0)
    ].copy()

    sepetteki_miktarlar = {}
    for k in st.session_state["cikis_sepeti"]:
        anahtar = (k["urun"], k["ozellik"])
        sepetteki_miktarlar[anahtar] = sepetteki_miktarlar.get(anahtar, 0) + int(k["adet"])

    if not ana_depo_stok.empty:
        ana_depo_stok["Kalan_Stok"] = ana_depo_stok.apply(
            lambda r: int(r["Mevcut Adet"])
            - sepetteki_miktarlar.get((r["Ürün"], r["Özellik"]), 0),
            axis=1,
        )
        sevk_edilebilir = ana_depo_stok[ana_depo_stok["Kalan_Stok"] > 0].copy()
    else:
        sevk_edilebilir = pd.DataFrame()

    if ana_depo_stok.empty and not st.session_state["cikis_sepeti"]:
        st.warning("İl Ana Depoda sevk edilebilecek stok bulunmuyor.")
    else:
        if not sevk_edilebilir.empty:
            sevk_edilebilir["Etiket"] = (
                sevk_edilebilir["Ürün"]
                + " | "
                + sevk_edilebilir["Özellik"]
                + " (Mevcut: "
                + sevk_edilebilir["Kalan_Stok"].astype(str)
                + ")"
            )

            secilen_etiket = st.selectbox(
                "Ürün ve Boyut",
                sevk_edilebilir["Etiket"].tolist(),
                key="sepet_urun_secim",
            )
            secilen_satir = sevk_edilebilir[sevk_edilebilir["Etiket"] == secilen_etiket].iloc[0]
            maks_adet = int(secilen_satir["Kalan_Stok"])

            urun_onizleme_karti_goster(
                secilen_satir["Ürün"],
                secilen_satir["Özellik"],
                f"Kalan Stok: {maks_adet:,}",
            )

            col_s1, col_s2 = st.columns([2, 1])
            eklenecek_adet = col_s1.number_input(
                "Adet",
                min_value=1,
                max_value=maks_adet,
                step=1,
                value=1,
                key="sepet_adet_input",
            )
            col_s2.write("")
            col_s2.write("")
            if col_s2.button("➕ Sepete Ekle", use_container_width=True):
                mevcut_sepet = st.session_state["cikis_sepeti"]
                guncellendi = False
                for item in mevcut_sepet:
                    if (
                        item["urun"] == secilen_satir["Ürün"]
                        and item["ozellik"] == secilen_satir["Özellik"]
                    ):
                        item["adet"] += int(eklenecek_adet)
                        guncellendi = True
                        break
                if not guncellendi:
                    mevcut_sepet.append(
                        {
                            "urun": secilen_satir["Ürün"],
                            "ozellik": secilen_satir["Özellik"],
                            "adet": int(eklenecek_adet),
                        }
                    )
                st.rerun()

        if st.session_state["cikis_sepeti"]:
            st.divider()
            sep_baslik_c1, sep_baslik_c2 = st.columns([4, 1])
            spekulum_sepet_kalemleri = [
                x
                for x in st.session_state["cikis_sepeti"]
                if x["urun"].strip().lower() == "spekulum"
            ]
            sepet_baslik = f"🛒 Sevk Sepeti ({len(st.session_state['cikis_sepeti'])} Kalem)"
            if len(spekulum_sepet_kalemleri) > 1:
                spekulum_sepet_toplam = sum(int(x["adet"]) for x in spekulum_sepet_kalemleri)
                sepet_baslik += f" — Spekulum Toplamı: {spekulum_sepet_toplam:,} Adet"

            sep_baslik_c1.subheader(sepet_baslik)
            if sep_baslik_c2.button("Temizle", use_container_width=True):
                st.session_state["cikis_sepeti"] = []
                st.rerun()

            for idx, item in enumerate(st.session_state["cikis_sepeti"]):
                gorsel = urun_gorsel_bilgisi(item["urun"], boyut=20)
                r_c1, r_c2 = st.columns([6, 1])
                with r_c1:
                    render_html(
                        f"""
                        <div class="cart-row">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                {gorsel['svg']}
                                <span><strong>{html.escape(item['urun'])}</strong> — {html.escape(item['ozellik'])}</span>
                            </div>
                            <span style="font-weight: 700; color: {gorsel['renk']};">{item['adet']:,} Adet</span>
                        </div>
                        """
                    )
                with r_c2:
                    if st.button("Çıkar", key=f"sepet_sil_{idx}", use_container_width=True):
                        st.session_state["cikis_sepeti"].pop(idx)
                        st.rerun()

            with st.form("ilce_toplu_cikis_form", clear_on_submit=True):
                c1, c2 = st.columns([1, 2])
                hedef_ilce = c1.selectbox("Hedef İlçe", aktif_ilceler)
                cikis_aciklama = c2.text_input("Açıklama (İsteğe bağlı)")

                if st.form_submit_button("Çıkışı Onayla ve Tutanak Oluştur", type="primary"):
                    sepet_kopya = [dict(x) for x in st.session_state["cikis_sepeti"]]
                    with st.spinner("Kaydediliyor..."):
                        eklenen_idler, kayit_zamani = toplu_ilce_cikis_ekle(
                            hedef_ilce,
                            sepet_kopya,
                            cikis_aciklama,
                        )
                    kayit_no_etiket = (
                        str(eklenen_idler[0])
                        if len(eklenen_idler) == 1
                        else f"{eklenen_idler[0]} - {eklenen_idler[-1]}"
                    )

                    st.session_state["son_cikis_tutanak"] = {
                        "kayit_no": kayit_no_etiket,
                        "tarih_saat": kayit_zamani,
                        "islem_turu": "ILCE_CIKIS",
                        "lokasyon": hedef_ilce,
                        "kalemler": sepet_kopya,
                        "aciklama": cikis_aciklama,
                    }
                    st.session_state["cikis_sepeti"] = []
                    st.success(f"{hedef_ilce} ilçesine {len(sepet_kopya)} kalem ürün çıkışı yapıldı.")
                    st.rerun()

    if "son_cikis_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_cikis_tutanak"], "son_cikis_tutanak")

# 4. SEKME: İLÇE SARF / ZAYİ GİRİŞİ
with sekme_sarf:
    ilce_mevcut_stoklar = (
        df_stok[(df_stok["Lokasyon"] != "İl Ana Depo") & (df_stok["Mevcut Adet"] > 0)].copy()
        if not df_stok.empty
        else pd.DataFrame()
    )

    if ilce_mevcut_stoklar.empty:
        st.warning("İlçelerde kullanılabilir stok bulunmuyor.")
    else:
        stoklu_ilceler = sorted(ilce_mevcut_stoklar["Lokasyon"].unique().tolist())
        s_col1, s_col2 = st.columns(2)
        sarf_ilce = s_col1.selectbox("İlçe", stoklu_ilceler, key="sarf_ilce_secim")

        secili_ilce_urunleri = ilce_mevcut_stoklar[
            ilce_mevcut_stoklar["Lokasyon"] == sarf_ilce
        ].copy()
        secili_ilce_urunleri["Etiket"] = (
            secili_ilce_urunleri["Ürün"]
            + " | "
            + secili_ilce_urunleri["Özellik"]
            + " (Mevcut: "
            + secili_ilce_urunleri["Mevcut Adet"].astype(str)
            + ")"
        )

        secilen_sarf_etiket = s_col2.selectbox(
            "Ürün ve Boyut",
            secili_ilce_urunleri["Etiket"].tolist(),
            key="sarf_urun_secim",
        )
        sarf_satir = secili_ilce_urunleri[
            secili_ilce_urunleri["Etiket"] == secilen_sarf_etiket
        ].iloc[0]
        ilce_maks_adet = int(sarf_satir["Mevcut Adet"])

        ilce_gecmis_sarf = df_hareket[
            (df_hareket["lokasyon"] == sarf_ilce)
            & (df_hareket["urun"] == sarf_satir["Ürün"])
            & (df_hareket["ozellik"] == sarf_satir["Özellik"])
        ]
        toplam_kullanilan = int(
            ilce_gecmis_sarf[ilce_gecmis_sarf["islem_turu"] == "ILCE_KULLANIM"]["adet"].sum()
        )
        toplam_zayi = int(
            ilce_gecmis_sarf[ilce_gecmis_sarf["islem_turu"] == "ILCE_ZAYI"]["adet"].sum()
        )

        urun_onizleme_karti_goster(
            sarf_satir["Ürün"],
            sarf_satir["Özellik"],
            f"Mevcut: {ilce_maks_adet:,}  |  Kullanılan: {toplam_kullanilan:,}  |  Zayi: {toplam_zayi:,}",
        )

        with st.form("ilce_sarf_zayi_form", clear_on_submit=True):
            f1, f2, f3 = st.columns([2, 1, 2])
            dusun_turu_secim = f1.radio(
                "Durum",
                ["Kullanılan", "Zayi"],
                horizontal=True,
            )
            sarf_adet = f2.number_input(
                "Adet",
                min_value=1,
                max_value=ilce_maks_adet,
                step=1,
                value=1,
            )
            sarf_aciklama = f3.text_input("Açıklama (İsteğe bağlı)")

            if st.form_submit_button("Stoktan Düş ve Kaydet", type="primary"):
                islem_kodu = (
                    "ILCE_KULLANIM" if dusun_turu_secim == "Kullanılan" else "ILCE_ZAYI"
                )

                with st.spinner("Kaydediliyor..."):
                    yeni_id, kayit_zamani = hareket_ekle(
                        islem_kodu,
                        sarf_ilce,
                        sarf_satir["Ürün"],
                        sarf_satir["Özellik"],
                        sarf_adet,
                        sarf_aciklama,
                    )
                st.session_state["son_sarf_tutanak"] = {
                    "kayit_no": yeni_id,
                    "tarih_saat": kayit_zamani,
                    "islem_turu": islem_kodu,
                    "lokasyon": sarf_ilce,
                    "kalemler": [
                        {
                            "urun": sarf_satir["Ürün"],
                            "ozellik": sarf_satir["Özellik"],
                            "adet": sarf_adet,
                        }
                    ],
                    "aciklama": sarf_aciklama,
                }
                st.success(
                    f"{sarf_ilce}: {sarf_adet:,} adet ({dusun_turu_secim}) stoktan düşüldü."
                )
                st.rerun()

    if "son_sarf_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_sarf_tutanak"], "son_sarf_tutanak")

# 5. SEKME: HAREKET GEÇMİŞİ
with sekme_gecmis:
    if df_hareket.empty:
        st.info("Henüz işlem kaydı yok.")
    else:
        df_goster_log = df_hareket.copy()
        df_goster_log["islem_turu"] = df_goster_log["islem_turu"].map(
            lambda x: ISLEM_ETIKETLERI.get(x, x)
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

        with st.expander("🖨️ Geçmiş Kayıt Tutanağı Yazdır"):
            kayit_nolar = df_hareket["id"].tolist()
            secilen_no = st.selectbox("Kayıt No", kayit_nolar)
            satir = df_hareket[df_hareket["id"] == secilen_no].iloc[0]

            ayni_sevkiyat = df_hareket[
                (df_hareket["tarih_saat"] == satir["tarih_saat"])
                & (df_hareket["islem_turu"] == satir["islem_turu"])
                & (df_hareket["lokasyon"] == satir["lokasyon"])
            ].sort_values(by="id")

            if len(ayni_sevkiyat) > 1:
                id_listesi = ayni_sevkiyat["id"].tolist()
                kayit_no_etiket = f"{id_listesi[0]} - {id_listesi[-1]}"
                kalem_listesi = [
                    {
                        "urun": r["urun"],
                        "ozellik": r["ozellik"],
                        "adet": int(r["adet"]),
                    }
                    for _, r in ayni_sevkiyat.iterrows()
                ]
            else:
                kayit_no_etiket = str(int(satir["id"]))
                kalem_listesi = [
                    {
                        "urun": satir["urun"],
                        "ozellik": satir["ozellik"],
                        "adet": int(satir["adet"]),
                    }
                ]

            gecmis_tutanak = {
                "kayit_no": kayit_no_etiket,
                "tarih_saat": satir["tarih_saat"],
                "islem_turu": satir["islem_turu"],
                "lokasyon": satir["lokasyon"],
                "kalemler": kalem_listesi,
                "aciklama": satir["aciklama"],
            }
            tutanak_paneli_goster(gecmis_tutanak)
