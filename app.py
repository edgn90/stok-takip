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

STANDART_KALEMLER = [
    ("HPV DNA Testi", "Standart"),
    ("Spekulum", "S"),
    ("Spekulum", "M"),
    ("Spekulum", "L"),
    ("Kargo Poşeti", "Standart"),
]

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
        .stok-tablo-wrap {
            width: 100%;
            overflow-x: auto;
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 12px;
            margin-bottom: 14px;
        }
        .stok-tablo {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .stok-tablo thead th {
            background: rgba(128, 128, 128, 0.08);
            border-bottom: 1px solid rgba(128, 128, 128, 0.25);
            border-right: 1px solid rgba(128, 128, 128, 0.15);
            padding: 12px 14px;
            text-align: center;
            vertical-align: middle;
            font-weight: 700;
            white-space: nowrap;
        }
        .stok-tablo thead th:first-child {
            text-align: left;
            min-width: 170px;
        }
        .stok-tablo thead th:last-child,
        .stok-tablo tbody td:last-child {
            border-right: none;
        }
        .th-urun-kutu {
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }
        .th-ikon-daire {
            width: 34px;
            height: 34px;
            border-radius: 9px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .stok-tablo tbody td {
            padding: 10px 14px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.14);
            border-right: 1px solid rgba(128, 128, 128, 0.12);
            text-align: center;
            font-variant-numeric: tabular-nums;
        }
        .stok-tablo tbody td:first-child {
            text-align: left;
            font-weight: 600;
        }
        .stok-tablo tbody tr:last-child td {
            border-bottom: none;
        }
        .stok-tablo tbody tr.ana-depo-satir {
            background: rgba(79, 70, 229, 0.07);
            font-weight: 700;
        }
        .stok-tablo tbody tr.ana-depo-satir td {
            border-bottom: 2px solid rgba(128, 128, 128, 0.25);
        }
        .stok-tablo tbody tr:hover {
            background: rgba(128, 128, 128, 0.05);
        }
        .bulk-item-box {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 0;
        }
        .bulk-item-title {
            font-size: 14.5px;
            font-weight: 700;
            line-height: 1.25;
        }
        .bulk-item-sub {
            font-size: 12px;
            opacity: 0.78;
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


def sade_stok_tablosu_goster(df_ozet: pd.DataFrame):
    """İlk (başlık) satırında ürün vektör ikonları ve ürün adları bulunan sade stok tablosu."""
    sutunlar = list(df_ozet.columns)
    baslik_hucreleri = []

    for col in sutunlar:
        if col == "Lokasyon":
            baslik_hucreleri.append("<th>Lokasyon</th>")
        else:
            temel_urun = col.split(" (")[0]
            gorsel = urun_gorsel_bilgisi(temel_urun, boyut=20)
            baslik_hucreleri.append(
                f"""
                <th>
                    <div class="th-urun-kutu">
                        <span class="th-ikon-daire" style="background: {gorsel['bg']};">{gorsel['svg']}</span>
                        <span style="color: {gorsel['renk']};">{html.escape(col)}</span>
                    </div>
                </th>
                """
            )

    govde_satirlari = []
    for _, row in df_ozet.iterrows():
        lok = str(row["Lokasyon"])
        satir_sinifi = ' class="ana-depo-satir"' if lok == "İl Ana Depo" else ""
        hucreler = [f"<td>{html.escape(lok)}</td>"]
        for col in sutunlar[1:]:
            deger = int(row[col])
            hucreler.append(f"<td>{deger:,}</td>")
        govde_satirlari.append(f"<tr{satir_sinifi}>{''.join(hucreler)}</tr>")

    tablo_html = f"""
    <div class="stok-tablo-wrap">
        <table class="stok-tablo">
            <thead>
                <tr>{''.join(baslik_hucreleri)}</tr>
            </thead>
            <tbody>
                {''.join(govde_satirlari)}
            </tbody>
        </table>
    </div>
    """
    render_html(tablo_html)


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


def toplu_hareket_ekle(
    islem_turu: str,
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
                islem_turu,
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


def key_olustur(on_ek: str, urun: str, ozellik: str) -> str:
    temiz = f"{urun}_{ozellik}".replace(" ", "_").replace("(", "").replace(")", "")
    return f"{on_ek}_{temiz}"


def adet_artir_cb(state_key: str, artis: int, maks_deger: int | None = None):
    mevcut = int(st.session_state.get(state_key, 0))
    yeni = mevcut + artis
    if maks_deger is not None:
        yeni = min(maks_deger, yeni)
    st.session_state[state_key] = yeni


def adet_ayarla_cb(state_key: str, hedef_deger: int):
    st.session_state[state_key] = int(hedef_deger)


# --- UYGULAMA ARAYÜZÜ ---
stil_uygula()

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

# 1. SEKME: SADE STOK DURUMU
with sekme_durum:
    if df_stok.empty:
        st.info("Henüz stok hareketi bulunmuyor.")
    else:
        df_ozet = sade_stok_ozeti_olustur(df_stok)
        sade_stok_tablosu_goster(df_ozet)

        st.download_button(
            label="📥 Ayrıntılı Excel Raporu İndir (.xlsx)",
            data=excel_verisi,
            file_name=dosya_adi,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sekme_excel_indir",
        )

# 2. SEKME: İL ANA DEPOYA TOPLU GİRİŞ + HIZLI ADET BUTONLARI
with sekme_giris:
    giris_kalem_listesi = list(STANDART_KALEMLER)
    if not df_stok.empty:
        for _, r in df_stok[["Ürün", "Özellik"]].drop_duplicates().iterrows():
            cift = (r["Ürün"], r["Özellik"])
            if cift not in giris_kalem_listesi:
                giris_kalem_listesi.append(cift)

    if st.session_state.pop("giris_sifirla_istegi", False):
        for urun_adi, ozellik in giris_kalem_listesi:
            st.session_state[key_olustur("giris_qty", urun_adi, ozellik)] = 0
        st.session_state["giris_yeni_urun_ad"] = ""
        st.session_state["giris_yeni_urun_ozellik"] = "Standart"
        st.session_state["giris_yeni_urun_adet"] = 0
        st.session_state["giris_aciklama_input"] = ""

    st.caption("Giriş yapmak istediğiniz ürünlerin yanına adet yazın veya hızlı butonları kullanın.")

    for urun_adi, ozellik in giris_kalem_listesi:
        w_key = key_olustur("giris_qty", urun_adi, ozellik)
        if w_key not in st.session_state:
            st.session_state[w_key] = 0

        mevcut_ana = (
            int(
                df_stok[
                    (df_stok["Lokasyon"] == "İl Ana Depo")
                    & (df_stok["Ürün"] == urun_adi)
                    & (df_stok["Özellik"] == ozellik)
                ]["Mevcut Adet"].sum()
            )
            if not df_stok.empty
            else 0
        )

        gorsel = urun_gorsel_bilgisi(urun_adi, boyut=22)
        etiket_baslik = (
            urun_adi if ozellik in ("", "Standart") else f"{urun_adi} ({ozellik})"
        )

        col_bilgi, col_input, col_b1, col_b2, col_b3, col_b4 = st.columns(
            [3.2, 1.6, 0.9, 0.9, 1.0, 0.8]
        )

        with col_bilgi:
            render_html(
                f"""
                <div class="bulk-item-box">
                    <div class="prod-icon-wrap" style="background: {gorsel['bg']};">
                        {gorsel['svg']}
                    </div>
                    <div>
                        <div class="bulk-item-title">{html.escape(etiket_baslik)}</div>
                        <div class="bulk-item-sub">Ana Depo Mevcut: <strong>{mevcut_ana:,}</strong></div>
                    </div>
                </div>
                """
            )

        with col_input:
            st.number_input(
                "Adet",
                min_value=0,
                step=1,
                key=w_key,
                label_visibility="collapsed",
            )

        with col_b1:
            st.button(
                "+50",
                key=f"{w_key}_p50",
                use_container_width=True,
                on_click=adet_artir_cb,
                args=(w_key, 50, None),
            )

        with col_b2:
            st.button(
                "+100",
                key=f"{w_key}_p100",
                use_container_width=True,
                on_click=adet_artir_cb,
                args=(w_key, 100, None),
            )

        with col_b3:
            st.button(
                "+500",
                key=f"{w_key}_p500",
                use_container_width=True,
                on_click=adet_artir_cb,
                args=(w_key, 500, None),
            )

        with col_b4:
            st.button(
                "0",
                key=f"{w_key}_rst",
                use_container_width=True,
                on_click=adet_ayarla_cb,
                args=(w_key, 0),
            )

    with st.expander("➕ Listede Olmayan Yeni Ürün Ekle"):
        ny_c1, ny_c2, ny_c3 = st.columns([2, 1.5, 1])
        ny_c1.text_input("Yeni Ürün Adı", key="giris_yeni_urun_ad")
        ny_c2.text_input("Özellik / Boyut", value="Standart", key="giris_yeni_urun_ozellik")
        ny_c3.number_input("Adet", min_value=0, step=1, value=0, key="giris_yeni_urun_adet")

    st.divider()
    g_alt1, g_alt2 = st.columns([2.5, 1.5])
    giris_aciklama = g_alt1.text_input(
        "Açıklama / İrsaliye No (İsteğe bağlı)",
        key="giris_aciklama_input",
    )

    toplam_girilecek_kalem = sum(
        1
        for urun_adi, ozellik in giris_kalem_listesi
        if st.session_state.get(key_olustur("giris_qty", urun_adi, ozellik), 0) > 0
    )
    if (
        st.session_state.get("giris_yeni_urun_ad", "").strip()
        and st.session_state.get("giris_yeni_urun_adet", 0) > 0
    ):
        toplam_girilecek_kalem += 1

    with g_alt2:
        st.write("")
        buton_etiket = (
            f"Kaydet ve Tutanak Oluştur ({toplam_girilecek_kalem} Kalem)"
            if toplam_girilecek_kalem > 0
            else "Kaydet ve Tutanak Oluştur"
        )
        if st.button(buton_etiket, type="primary", use_container_width=True, key="btn_toplu_giris"):
            girilecek_kalemler = []
            for urun_adi, ozellik in giris_kalem_listesi:
                miktar = int(st.session_state.get(key_olustur("giris_qty", urun_adi, ozellik), 0))
                if miktar > 0:
                    girilecek_kalemler.append(
                        {"urun": urun_adi, "ozellik": ozellik, "adet": miktar}
                    )

            yeni_u_ad = st.session_state.get("giris_yeni_urun_ad", "").strip()
            yeni_u_oz = st.session_state.get("giris_yeni_urun_ozellik", "").strip() or "Standart"
            yeni_u_ad_miktar = int(st.session_state.get("giris_yeni_urun_adet", 0))
            if yeni_u_ad and yeni_u_ad_miktar > 0:
                girilecek_kalemler.append(
                    {"urun": yeni_u_ad, "ozellik": yeni_u_oz, "adet": yeni_u_ad_miktar}
                )

            if not girilecek_kalemler:
                st.error("En az bir ürün için 0'dan büyük adet girmelisiniz.")
            else:
                with st.spinner("Kaydediliyor..."):
                    eklenen_idler, kayit_zamani = toplu_hareket_ekle(
                        "ANA_DEPO_GIRIS",
                        "İl Ana Depo",
                        girilecek_kalemler,
                        giris_aciklama,
                    )
                kayit_no_etiket = (
                    str(eklenen_idler[0])
                    if len(eklenen_idler) == 1
                    else f"{eklenen_idler[0]} - {eklenen_idler[-1]}"
                )
                st.session_state["son_giris_tutanak"] = {
                    "kayit_no": kayit_no_etiket,
                    "tarih_saat": kayit_zamani,
                    "islem_turu": "ANA_DEPO_GIRIS",
                    "lokasyon": "İl Ana Depo",
                    "kalemler": girilecek_kalemler,
                    "aciklama": giris_aciklama,
                }
                st.session_state["giris_sifirla_istegi"] = True
                st.success(f"İl Ana Depoya {len(girilecek_kalemler)} kalem ürün girişi kaydedildi.")
                st.rerun()

    if "son_giris_tutanak" in st.session_state:
        tutanak_paneli_goster(st.session_state["son_giris_tutanak"], "son_giris_tutanak")

# 3. SEKME: İLÇEYE TOPLU ÇIKIŞ + HIZLI ADET BUTONLARI
with sekme_cikis:
    ana_depo_stok = (
        df_stok[(df_stok["Lokasyon"] == "İl Ana Depo") & (df_stok["Mevcut Adet"] > 0)].copy()
        if not df_stok.empty
        else pd.DataFrame()
    )

    if ana_depo_stok.empty:
        st.warning("İl Ana Depoda sevk edilebilecek stok bulunmuyor.")
    else:
        mevcut_harita = {
            (r["Ürün"], r["Özellik"]): int(r["Mevcut Adet"])
            for _, r in ana_depo_stok.iterrows()
        }
        cikis_kalem_listesi = [
            (u, oz, mevcut_harita[(u, oz)])
            for u, oz in STANDART_KALEMLER
            if (u, oz) in mevcut_harita
        ]
        for (u, oz), mikt in mevcut_harita.items():
            if (u, oz) not in STANDART_KALEMLER:
                cikis_kalem_listesi.append((u, oz, mikt))

        if st.session_state.pop("cikis_sifirla_istegi", False):
            for u, oz, _ in cikis_kalem_listesi:
                st.session_state[key_olustur("cikis_qty", u, oz)] = 0
            st.session_state["cikis_aciklama_input"] = ""

        hedef_ilce = st.selectbox("Hedef İlçe", aktif_ilceler, key="toplu_cikis_ilce")
        st.caption(
            f"**{hedef_ilce}** ilçesine sevk edilecek adetleri girin veya hızlı butonları kullanın."
        )

        for urun_adi, ozellik, maks_adet in cikis_kalem_listesi:
            w_key = key_olustur("cikis_qty", urun_adi, ozellik)
            if w_key not in st.session_state:
                st.session_state[w_key] = 0
            elif st.session_state[w_key] > maks_adet:
                st.session_state[w_key] = maks_adet

            ilce_mevcut = (
                int(
                    df_stok[
                        (df_stok["Lokasyon"] == hedef_ilce)
                        & (df_stok["Ürün"] == urun_adi)
                        & (df_stok["Özellik"] == ozellik)
                    ]["Mevcut Adet"].sum()
                )
                if not df_stok.empty
                else 0
            )

            gorsel = urun_gorsel_bilgisi(urun_adi, boyut=22)
            etiket_baslik = (
                urun_adi if ozellik in ("", "Standart") else f"{urun_adi} ({ozellik})"
            )

            col_bilgi, col_input, col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(
                [3.1, 1.5, 0.85, 0.85, 0.9, 0.95, 0.7]
            )

            with col_bilgi:
                render_html(
                    f"""
                    <div class="bulk-item-box">
                        <div class="prod-icon-wrap" style="background: {gorsel['bg']};">
                            {gorsel['svg']}
                        </div>
                        <div>
                            <div class="bulk-item-title">{html.escape(etiket_baslik)}</div>
                            <div class="bulk-item-sub">Ana Depo: <strong>{maks_adet:,}</strong> &nbsp;|&nbsp; {html.escape(hedef_ilce)}: <strong>{ilce_mevcut:,}</strong></div>
                        </div>
                    </div>
                    """
                )

            with col_input:
                st.number_input(
                    "Adet",
                    min_value=0,
                    max_value=maks_adet,
                    step=1,
                    key=w_key,
                    label_visibility="collapsed",
                )

            with col_b1:
                st.button(
                    "+25",
                    key=f"{w_key}_p25",
                    use_container_width=True,
                    on_click=adet_artir_cb,
                    args=(w_key, 25, maks_adet),
                )

            with col_b2:
                st.button(
                    "+50",
                    key=f"{w_key}_p50",
                    use_container_width=True,
                    on_click=adet_artir_cb,
                    args=(w_key, 50, maks_adet),
                )

            with col_b3:
                st.button(
                    "+100",
                    key=f"{w_key}_p100",
                    use_container_width=True,
                    on_click=adet_artir_cb,
                    args=(w_key, 100, maks_adet),
                )

            with col_b4:
                st.button(
                    "Hepsi",
                    key=f"{w_key}_all",
                    use_container_width=True,
                    on_click=adet_ayarla_cb,
                    args=(w_key, maks_adet),
                )

            with col_b5:
                st.button(
                    "0",
                    key=f"{w_key}_rst",
                    use_container_width=True,
                    on_click=adet_ayarla_cb,
                    args=(w_key, 0),
                )

        st.divider()
        c_alt1, c_alt2 = st.columns([2.5, 1.5])
        cikis_aciklama = c_alt1.text_input(
            "Açıklama (İsteğe bağlı)",
            key="cikis_aciklama_input",
        )

        toplam_cikilacak_kalem = sum(
            1
            for u, oz, _ in cikis_kalem_listesi
            if st.session_state.get(key_olustur("cikis_qty", u, oz), 0) > 0
        )

        with c_alt2:
            st.write("")
            cikis_buton_etiket = (
                f"Çıkışı Onayla ve Tutanak Oluştur ({toplam_cikilacak_kalem} Kalem)"
                if toplam_cikilacak_kalem > 0
                else "Çıkışı Onayla ve Tutanak Oluştur"
            )
            if st.button(
                cikis_buton_etiket,
                type="primary",
                use_container_width=True,
                key="btn_toplu_cikis",
            ):
                cikilacak_kalemler = []
                for u, oz, _ in cikis_kalem_listesi:
                    miktar = int(st.session_state.get(key_olustur("cikis_qty", u, oz), 0))
                    if miktar > 0:
                        cikilacak_kalemler.append(
                            {"urun": u, "ozellik": oz, "adet": miktar}
                        )

                if not cikilacak_kalemler:
                    st.error("Sevk etmek için en az bir ürüne 0'dan büyük adet girmelisiniz.")
                else:
                    with st.spinner("Kaydediliyor..."):
                        eklenen_idler, kayit_zamani = toplu_hareket_ekle(
                            "ILCE_CIKIS",
                            hedef_ilce,
                            cikilacak_kalemler,
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
                        "kalemler": cikilacak_kalemler,
                        "aciklama": cikis_aciklama,
                    }
                    st.session_state["cikis_sifirla_istegi"] = True
                    st.success(
                        f"{hedef_ilce} ilçesine {len(cikilacak_kalemler)} kalem ürün çıkışı yapıldı."
                    )
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
