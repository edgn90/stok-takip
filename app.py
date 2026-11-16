import html
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from gspread.exceptions import WorksheetNotFound

st.set_page_config(page_title="İl-İlçe Stok Takip", page_icon="📦", layout="wide")

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


def render_html(raw_html: str):
    """Markdown kod bloğu çakışmasını önlemek için satır başı boşluklarını temizler."""
    temiz = "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())
    st.markdown(temiz, unsafe_allow_html=True)


def urun_gorsel_bilgisi(urun_adi: str, boyut: int = 26) -> dict:
    """Her ürün için modern minimalist vektör SVG ikonu ve renk paleti döndürür."""
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
        .app-header {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 8px;
        }
        .app-logo-box {
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: rgba(37, 99, 235, 0.12);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .app-title-text {
            font-size: 26px;
            font-weight: 700;
            margin: 0;
            line-height: 1.2;
        }
        .app-sub-text {
            font-size: 13.5px;
            opacity: 0.72;
            margin: 2px 0 0 0;
        }
        .prod-card {
            border: 1px solid rgba(128, 128, 128, 0.22);
            border-radius: 14px;
            padding: 15px 16px;
            margin-bottom: 12px;
            transition: border-color 0.2s ease;
        }
        .prod-card:hover {
            border-color: rgba(128, 128, 128, 0.45);
        }
        .prod-card-top {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
        }
        .prod-icon-wrap {
            width: 44px;
            height: 44px;
            border-radius: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .prod-name {
            font-size: 15px;
            font-weight: 600;
            margin: 0;
        }
        .prod-total {
            font-size: 22px;
            font-weight: 700;
            margin: 0;
            line-height: 1.2;
        }
        .prod-meta {
            display: flex;
            justify-content: space-between;
            font-size: 12.5px;
            opacity: 0.82;
            padding-top: 8px;
            border-top: 1px solid rgba(128, 128, 128, 0.16);
        }
        .size-pills {
            display: flex;
            gap: 6px;
            margin-top: 8px;
            flex-wrap: wrap;
        }
        .size-pill {
            font-size: 11.5px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 999px;
            background: rgba(13, 148, 136, 0.12);
            color: #0D9488;
        }
        .preview-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            border: 1px solid rgba(128, 128, 128, 0.24);
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0 14px 0;
        }
        .preview-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .preview-badge {
            font-size: 12.5px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 8px;
            background: rgba(128, 128, 128, 0.12);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 10px 16px;
            border-radius: 8px 8px 0 0;
            font-weight: 600;
        }
        </style>
        """
    )


def urun_onizleme_karti_goster(urun_adi: str, ozellik: str, stok_bilgisi: str):
    gorsel = urun_gorsel_bilgisi(urun_adi, boyut=26)
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
                    <div style="font-weight: 600; font-size: 15px;">{guvenli_urun}</div>
                    <div style="font-size: 12.5px; opacity: 0.78;">Özellik / Boyut: <strong>{guvenli_ozellik}</strong></div>
                </div>
            </div>
            <div class="preview-badge">{guvenli_stok}</div>
        </div>
        """
    )


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


def tutanak_html_olustur(veri: dict) -> str:
    kayit_no = html.escape(str(veri.get("kayit_no", "-")))
    tarih_saat = html.escape(str(veri.get("tarih_saat", "-")))
    islem_turu = veri.get("islem_turu", "")
    lokasyon = html.escape(str(veri.get("lokasyon", "-")))
    urun_ham = str(veri.get("urun", "-"))
    urun = html.escape(urun_ham)
    ozellik = html.escape(str(veri.get("ozellik", "-")))
    adet = html.escape(str(veri.get("adet", "-")))
    aciklama = html.escape(str(veri.get("aciklama", "")).strip() or "-")
    teslim_eden = html.escape(str(veri.get("teslim_eden", "")).strip())
    teslim_alan = html.escape(str(veri.get("teslim_alan", "")).strip())
    urun_svg = urun_gorsel_bilgisi(urun_ham, boyut=18)["svg"]

    if islem_turu == "ANA_DEPO_GIRIS":
        islem_baslik = "İL ANA DEPO GİRİŞ TUTANAĞI"
        gonderen_birim = "Tedarikçi / Gönderen Birim"
        alan_birim = "İstanbul İl Ana Depo"
        beyan_metni = (
            "Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler eksiksiz ve sağlam "
            "olarak İl Ana Depo stoklarına teslim alınmıştır."
        )
    else:
        islem_baslik = "İLÇE MALZEME SEVK VE TESLİM TUTANAĞI"
        gonderen_birim = "İstanbul İl Ana Depo"
        alan_birim = f"{lokasyon} İlçe Birimi"
        beyan_metni = (
            f"Yukarıda cinsi, özelliği ve miktarı belirtilen malzemeler İl Ana Depodan çıkış "
            f"yapılarak {alan_birim} yetkilisine eksiksiz ve sağlam olarak teslim edilmiştir."
        )

    teslim_eden_satir = teslim_eden if teslim_eden else ".........................................."
    teslim_alan_satir = teslim_alan if teslim_alan else ".........................................."

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Teslim Tesellüm Tutanağı - No {kayit_no}</title>
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
    padding: 10px;
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
      <h1>MALZEME TESLİM - TESELLÜM TUTANAĞI</h1>
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
        <td class="meta-label">Teslim Eden Birim</td>
        <td>{gonderen_birim}</td>
        <td class="meta-label">Teslim Alan Birim</td>
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
        <tr>
          <td>1</td>
          <td><div class="item-cell-flex">{urun_svg}<strong>{urun}</strong></div></td>
          <td>{ozellik}</td>
          <td><strong>{adet} Adet</strong></td>
        </tr>
      </tbody>
    </table>

    <div class="note-box">
      <strong>Açıklama / İrsaliye Bilgisi:</strong> {aciklama}
    </div>

    <div class="declaration">
      {beyan_metni} İşbu tutanak 2 (iki) nüsha olarak düzenlenmiş ve taraflarca imza altına alınmıştır.
    </div>

    <div class="signatures">
      <div class="sig-box">
        <div class="sig-title">TESLİM EDEN</div>
        <div class="sig-line"><strong>Adı Soyadı:</strong> {teslim_eden_satir}</div>
        <div class="sig-line"><strong>Unvanı:</strong> ...............................................</div>
        <div class="sig-line"><strong>Tarih:</strong> {tarih_saat.split(' ')[0]}</div>
        <div class="sig-line" style="margin-top: 22px;"><strong>İmza:</strong></div>
      </div>
      <div class="sig-box">
        <div class="sig-title">TESLİM ALAN</div>
        <div class="sig-line"><strong>Adı Soyadı:</strong> {teslim_alan_satir}</div>
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
    ust_c1.subheader(f"📄 Otomatik Tutanak (Kayıt #{tutanak_verisi['kayit_no']})")
    ust_c2.download_button(
        label="⬇️ Tutanağı Dosya İndir",
        data=html_kod.encode("utf-8"),
        file_name=f"tutanak_no_{tutanak_verisi['kayit_no']}.html",
        mime="text/html",
        use_container_width=True,
        key=f"dl_{session_key}_{tutanak_verisi['kayit_no']}",
    )
    if session_key and ust_c3.button("✖ Kapat", use_container_width=True, key=f"close_{session_key}"):
        del st.session_state[session_key]
        st.rerun()

    components.html(html_kod, height=660, scrolling=True)


# --- UYGULAMA ARAYÜZÜ ---
stil_uygula()

render_html(
    """
    <div class="app-header">
        <div class="app-logo-box">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
        </div>
        <div>
            <div class="app-title-text">İl-İlçe Stok Takip Sistemi</div>
            <div class="app-sub-text">İstanbul İl Ana Depo ve 39 İlçe Anlık Malzeme Yönetimi</div>
        </div>
    </div>
    """
)

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

col_m1.metric("🏢 İl Ana Depo Toplam", f"{ana_depo_toplam:,}")
col_m2.metric("📍 İlçeler Toplam", f"{ilce_toplam:,}")
col_m3.metric("📦 Genel Toplam", f"{ana_depo_toplam + ilce_toplam:,}")

with col_aksiyon:
    excel_verisi = excel_olustur(df_stok, df_hareket)
    dosya_adi = f"stok_raporu_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        label="📊 Excel İndir (.xlsx)",
        data=excel_verisi,
        file_name=dosya_adi,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    if st.button("🔄 Tabloyu Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

sekme_durum, sekme_giris, sekme_cikis, sekme_gecmis = st.tabs(
    [
        "📊 Anlık Stok Durumu",
        "📥 İl Ana Depoya Giriş",
        "📤 İlçeye Çıkış Yap",
        "📋 Hareket Geçmişi",
    ]
)

# 1. SEKME: ANLIK STOK
with sekme_durum:
    # Üstte 3 Temel Ürün için Modern Vektör Özet Kartları
    kart_sutunlari = st.columns(3)
    for idx, (urun_adi, ozellikler) in enumerate(URUN_KATALOGU.items()):
        gorsel = urun_gorsel_bilgisi(urun_adi, boyut=24)
        if df_stok.empty:
            ana_adet = 0
            ilce_adet = 0
        else:
            u_df = df_stok[df_stok["Ürün"] == urun_adi]
            ana_adet = int(u_df[u_df["Lokasyon"] == "İl Ana Depo"]["Mevcut Adet"].sum())
            ilce_adet = int(u_df[u_df["Lokasyon"] != "İl Ana Depo"]["Mevcut Adet"].sum())

        toplam_urun = ana_adet + ilce_adet

        beden_html = ""
        if len(ozellikler) > 1:
            pills = []
            for oz in ozellikler:
                oz_ana = (
                    int(
                        df_stok[
                            (df_stok["Ürün"] == urun_adi)
                            & (df_stok["Özellik"] == oz)
                            & (df_stok["Lokasyon"] == "İl Ana Depo")
                        ]["Mevcut Adet"].sum()
                    )
                    if not df_stok.empty
                    else 0
                )
                pills.append(f'<span class="size-pill">{oz}: {oz_ana} Ana Depo</span>')
            beden_html = f'<div class="size-pills">{"".join(pills)}</div>'

        with kart_sutunlari[idx]:
            render_html(
                f"""
                <div class="prod-card">
                    <div class="prod-card-top">
                        <div class="prod-icon-wrap" style="background: {gorsel['bg']};">
                            {gorsel['svg']}
                        </div>
                        <div>
                            <div class="prod-name">{html.escape(urun_adi)}</div>
                            <div class="prod-total" style="color: {gorsel['renk']};">{toplam_urun:,} <span style="font-size: 13px; font-weight: 500; opacity: 0.75;">Adet</span></div>
                        </div>
                    </div>
                    <div class="prod-meta">
                        <span>Ana Depo: <strong>{ana_adet:,}</strong></span>
                        <span>İlçeler: <strong>{ilce_adet:,}</strong></span>
                    </div>
                    {beden_html}
                </div>
                """
            )

    if df_stok.empty:
        st.info(
            "Henüz stok hareketi bulunmuyor. '📥 İl Ana Depoya Giriş' sekmesinden ilk kaydı ekleyebilirsiniz."
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
    st.caption(f"⏱️ Kayıt zamanı otomatik atanacaktır (Şu an: {simdi_str()})")

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
        f"Ana Depoda Mevcut: {mevcut_ana_stok:,} Adet",
    )

    with st.form("ana_depo_giris_form", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        giris_adet = c1.number_input("Giriş Adedi", min_value=1, step=1, value=1)
        giris_aciklama = c2.text_input("Açıklama / İrsaliye No (İsteğe bağlı)")

        ci1, ci2 = st.columns(2)
        giris_teslim_eden = ci1.text_input("Tutanak: Teslim Eden Adı Soyadı (İsteğe bağlı)")
        giris_teslim_alan = ci2.text_input("Tutanak: Teslim Alan Adı Soyadı (İsteğe bağlı)")

        if st.form_submit_button("Ana Depoya Kaydet ve Tutanak Oluştur", type="primary"):
            temiz_urun = final_urun.strip()
            temiz_ozellik = final_ozellik.strip() if final_ozellik.strip() else "Standart"

            if not temiz_urun:
                st.error("Ürün adı boş bırakılamaz.")
            else:
                with st.spinner("Google Sheets'e kaydediliyor..."):
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
                    "urun": temiz_urun,
                    "ozellik": temiz_ozellik,
                    "adet": giris_adet,
                    "aciklama": giris_aciklama,
                    "teslim_eden": giris_teslim_eden,
                    "teslim_alan": giris_teslim_alan,
                }
                st.success(
                    f"{temiz_urun} ({temiz_ozellik}) - {giris_adet} adet İl Ana Depoya eklendi. Tutanak aşağıda hazırlandı."
                )
                st.rerun()

    if "son_giris_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_giris_tutanak"], "son_giris_tutanak")

# 3. SEKME: İLÇEYE ÇIKIŞ
with sekme_cikis:
    st.caption(f"⏱️ Çıkış zamanı otomatik atanacaktır (Şu an: {simdi_str()})")
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

        secilen_etiket = st.selectbox(
            "Ana Depodan Çıkılacak Ürün ve Özellik", ana_depo_stok["Etiket"].tolist()
        )
        secilen_satir = ana_depo_stok[ana_depo_stok["Etiket"] == secilen_etiket].iloc[0]
        maks_adet = int(secilen_satir["Mevcut Adet"])

        urun_onizleme_karti_goster(
            secilen_satir["Ürün"],
            secilen_satir["Özellik"],
            f"Sevk Edilebilir Stok: {maks_adet:,} Adet",
        )

        with st.form("ilce_cikis_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            hedef_ilce = c1.selectbox("Hedef İlçe", aktif_ilceler)
            cikis_adet = c2.number_input(
                "Çıkış Adedi", min_value=1, max_value=maks_adet, step=1, value=1
            )
            cikis_aciklama = st.text_input("Açıklama (İsteğe bağlı)")

            cc1, cc2 = st.columns(2)
            cikis_teslim_eden = cc1.text_input("Tutanak: Teslim Eden Adı Soyadı (İsteğe bağlı)")
            cikis_teslim_alan = cc2.text_input("Tutanak: Teslim Alan Adı Soyadı (İsteğe bağlı)")

            if st.form_submit_button("İlçeye Çıkışı Onayla ve Tutanak Oluştur", type="primary"):
                with st.spinner("Google Sheets güncelleniyor..."):
                    yeni_id, kayit_zamani = hareket_ekle(
                        "ILCE_CIKIS",
                        hedef_ilce,
                        secilen_satir["Ürün"],
                        secilen_satir["Özellik"],
                        cikis_adet,
                        cikis_aciklama,
                    )
                st.session_state["son_cikis_tutanak"] = {
                    "kayit_no": yeni_id,
                    "tarih_saat": kayit_zamani,
                    "islem_turu": "ILCE_CIKIS",
                    "lokasyon": hedef_ilce,
                    "urun": secilen_satir["Ürün"],
                    "ozellik": secilen_satir["Özellik"],
                    "adet": cikis_adet,
                    "aciklama": cikis_aciklama,
                    "teslim_eden": cikis_teslim_eden,
                    "teslim_alan": cikis_teslim_alan,
                }
                st.success(
                    f"{secilen_satir['Ürün']} ({secilen_satir['Özellik']}) - {cikis_adet} adet {hedef_ilce} stoğuna aktarıldı. Tutanak aşağıda hazırlandı."
                )
                st.rerun()

    if "son_cikis_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_cikis_tutanak"], "son_cikis_tutanak")

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

        with st.expander("🖨️ Geçmiş Bir Kaydın Tutanağını Yeniden Yazdır"):
            kayit_nolar = df_hareket["id"].tolist()
            secilen_no = st.selectbox("Tutanak Yazdırılacak Kayıt No", kayit_nolar)
            satir = df_hareket[df_hareket["id"] == secilen_no].iloc[0]
            gecmis_tutanak = {
                "kayit_no": int(satir["id"]),
                "tarih_saat": satir["tarih_saat"],
                "islem_turu": satir["islem_turu"],
                "lokasyon": satir["lokasyon"],
                "urun": satir["urun"],
                "ozellik": satir["ozellik"],
                "adet": int(satir["adet"]),
                "aciklama": satir["aciklama"],
                "teslim_eden": "",
                "teslim_alan": "",
            }
            tutanak_paneli_goster(gecmis_tutanak)
