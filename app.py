"""
Kansallisarkiston Sisältöhaku-työkalu
Sukututkimuksen ja historiallisen aineiston hakutyökalu
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import re
import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import uuid
from dotenv import load_dotenv

load_dotenv()

ES_URL = "https://es.demo.kansallisarkisto.fi"

# Korostusmerkit, jotka eivät esiinny asiakirjateksteissä. Muutetaan <mark>-tageiksi
# vasta kun teksti on turvallisesti escapattu.
KOROSTUS_ALKU = "\u0002"
KOROSTUS_LOPPU = "\u0003"

NIMIVARIAATIOT = {
    "juho": ["juho", "johan", "johannes", "juhana", "juhani"],
    "maria": ["maria", "maaria", "mari", "marja", "margareta", "maaret"],
    "anna": ["anna", "anne", "annikki", "annakaisa"],
    "heikki": ["heikki", "henrik", "henrikki", "henric"],
    "matti": ["matti", "matts", "mattias", "matthias"],
    "kalle": ["kalle", "karl", "carolus", "kaarlo"],
    "liisa": ["liisa", "lisa", "elisabet", "elisabetha"],
    "erkki": ["erkki", "eric", "erik", "ericus"],
    "pekka": ["pekka", "petrus", "pietari", "peter"],
    "tuomas": ["tuomas", "thomas", "tomas"],
    "jaakko": ["jaakko", "jacob", "jakob", "jaakob"],
    "mikko": ["mikko", "michel", "michael", "mikael"],
    "riitta": ["riitta", "britta", "brita", "margareta"],
    "kaisa": ["kaisa", "kajsa", "katarina", "katharina"],
}

INDEKSIT = {
    "Tuomiokirjat (1600–1900-luvut)": "tuomiokirjat",
    "Voudintilit (1537–1634)": "voudintilit",
    "Diplomatarium Fennicum (Keskiaika)": "df",
    "Kaikki aineistot": "tuomiokirjat,voudintilit,df",
}


def on_yhdistelma(indeksi):
    """Onko kyseessä usean aineiston yhdistelmähaku (esim. Kaikki aineistot)."""
    return "," in (indeksi or "")


def tuloksen_indeksi(src, indeksi_avain):
    """Päättelee yksittäisen tuloksen aineiston. Yhdistelmähaussa DF tunnistetaan sen kentistä."""
    if not on_yhdistelma(indeksi_avain):
        return indeksi_avain
    return "df" if ("transcript" in src or "dating_start_year" in src) else "tuomiokirjat"


def teksti_kentat(indeksi):
    """Tekstikentät, joista haetaan. DF:ssä teksti on kentässä 'transcript'."""
    if indeksi == "df":
        return ["transcript"]
    if on_yhdistelma(indeksi) and "df" in indeksi.split(","):
        return ["teksti", "transcript"]
    return ["teksti"]

ASIASANAT = {
    "Oikeudenkäynti": ["tuomio", "käräjä", "syyte", "vastaaja", "kantaja", "sakko", "rangaistus", "oikeus", "dom", "rätt", "sak", "böter", "straff"],
    "Kauppa ja velka": ["kauppa", "velka", "maksu", "myynti", "osto", "handel", "skuld", "betalning", "köp", "sälj", "köpman"],
    "Perintö ja omaisuus": ["perintö", "testamentti", "tila", "maa", "omaisuus", "arv", "testamente", "gård", "jord", "egendom", "hemman"],
    "Henkilö": ["nimeltä", "poika", "tytär", "vaimo", "mies", "leski", "son", "dotter", "hustru", "man", "änka", "enka"],
    "Kirkko ja uskonto": ["kirkko", "pappi", "seurakunta", "kyrka", "präst", "församling", "noita", "taikuus", "häxeri"],
    "Väkivalta": ["tappo", "murha", "haavoitti", "löi", "mord", "dråp", "slagsmål", "sår"],
    "Maatalous": ["talo", "torppari", "ratsutila", "pelto", "heinä", "hevonen", "bonde", "torpare", "åker", "häst"],
}

# ── Aineistokokonaisuus → Maakunta -hakemisto ─────────────────────────────────
# Avain = sana joka esiintyy aineistokokonaisuuden alussa (ennen "tuomiokunnan" tms.)
# Arvo = maakunta
AINEISTO_MAAKUNTA = {
    # Etelä-Pohjanmaa
    "Etelä-Pohjanmaan": "Etelä-Pohjanmaa",
    "Ilmajoen": "Etelä-Pohjanmaa",
    "Kauhajoen": "Etelä-Pohjanmaa",
    "Lapuan": "Etelä-Pohjanmaa",
    "Alavuden": "Etelä-Pohjanmaa",
    "Kuortaneen": "Etelä-Pohjanmaa",
    "Lappajärven": "Etelä-Pohjanmaa",
    "Evijärven": "Etelä-Pohjanmaa",
    "Isojoen": "Etelä-Pohjanmaa",
    "Jurvan": "Etelä-Pohjanmaa",
    "Karijoen": "Etelä-Pohjanmaa",
    "Teuvan": "Etelä-Pohjanmaa",
    "Isokyrön": "Etelä-Pohjanmaa",
    "Ylistaron": "Etelä-Pohjanmaa",
    "Seinäjoen": "Etelä-Pohjanmaa",
    "Jalasjärven": "Etelä-Pohjanmaa",
    "Kurikka": "Etelä-Pohjanmaa",
    "Kurikan": "Etelä-Pohjanmaa",
    # Pohjanmaa (rannikko)
    "Pohjanmaan": "Pohjanmaa",
    "Vaasan": "Pohjanmaa",
    "Närpiön": "Pohjanmaa",
    "Uudenkaarlepyyn": "Pohjanmaa",
    "Isokaarlepyyn": "Pohjanmaa",
    "Mustasaaren": "Pohjanmaa",
    "Maalahden": "Pohjanmaa",
    "Kristiinankaupungin": "Pohjanmaa",
    "Kaskisten": "Pohjanmaa",
    "Oravaisten": "Pohjanmaa",
    # Keski-Pohjanmaa
    "Keski-Pohjanmaan": "Keski-Pohjanmaa",
    "Kokkolan": "Keski-Pohjanmaa",
    "Kruunupyyn": "Keski-Pohjanmaa",
    "Kaustisen": "Keski-Pohjanmaa",
    "Vetelin": "Keski-Pohjanmaa",
    "Kannuksen": "Keski-Pohjanmaa",
    "Toholammin": "Keski-Pohjanmaa",
    # Pirkanmaa
    "Tyrvään": "Pirkanmaa",
    "Ikaalisten": "Pirkanmaa",
    "Tampereen": "Pirkanmaa",
    "Tammelan": "Pirkanmaa",
    "Pirkkalan": "Pirkanmaa",
    "Ruoveden": "Pirkanmaa",
    "Laukaan": "Pirkanmaa",
    "Ylöjärven": "Pirkanmaa",
    "Kangasalan": "Pirkanmaa",
    "Hämeenkyrön": "Pirkanmaa",
    "Urjalan": "Pirkanmaa",
    "Vammalan": "Pirkanmaa",
    # Varsinais-Suomi
    "Turun": "Varsinais-Suomi",
    "Rauman": "Varsinais-Suomi",
    "Salon": "Varsinais-Suomi",
    "Loimaan": "Varsinais-Suomi",
    "Maskun": "Varsinais-Suomi",
    "Paimion": "Varsinais-Suomi",
    "Paraisten": "Varsinais-Suomi",
    "Mynämäen": "Varsinais-Suomi",
    "Naantalin": "Varsinais-Suomi",
    "Uudenkaupungin": "Varsinais-Suomi",
    "Halikko": "Varsinais-Suomi",
    "Halikon": "Varsinais-Suomi",
    "Perniön": "Varsinais-Suomi",
    "Vehmaan": "Varsinais-Suomi",
    # Satakunta
    "Porin": "Satakunta",
    "Ulvilan": "Satakunta",
    "Euran": "Satakunta",
    "Kokemäen": "Satakunta",
    "Huittisten": "Satakunta",
    "Harjavallan": "Satakunta",
    "Raaseporin": "Satakunta",
    # Häme
    "Hämeenlinnan": "Kanta-Häme",
    "Tammelan": "Kanta-Häme",
    "Forssan": "Kanta-Häme",
    "Riihimäen": "Kanta-Häme",
    "Janakkalan": "Kanta-Häme",
    "Hattulan": "Kanta-Häme",
    "Hausjärven": "Kanta-Häme",
    "Lopun": "Kanta-Häme",
    # Päijät-Häme
    "Lahden": "Päijät-Häme",
    "Hollolan": "Päijät-Häme",
    "Heinolan": "Päijät-Häme",
    "Nastolan": "Päijät-Häme",
    "Asikkalan": "Päijät-Häme",
    "Sysmän": "Päijät-Häme",
    # Uusimaa
    "Helsingin": "Uusimaa",
    "Espoon": "Uusimaa",
    "Vantaan": "Uusimaa",
    "Porvoon": "Uusimaa",
    "Lohjan": "Uusimaa",
    "Hyvinkään": "Uusimaa",
    "Järvenpään": "Uusimaa",
    "Nurmijärven": "Uusimaa",
    "Tuusulan": "Uusimaa",
    "Kirkkonummen": "Uusimaa",
    "Sipoon": "Uusimaa",
    "Tammisaaren": "Uusimaa",
    "Hangon": "Uusimaa",
    "Loviisan": "Uusimaa",
    # Kymenlaakso
    "Kotkan": "Kymenlaakso",
    "Kouvolan": "Kymenlaakso",
    "Haminan": "Kymenlaakso",
    "Imatran": "Kymenlaakso",
    "Elimäen": "Kymenlaakso",
    "Anjalankosken": "Kymenlaakso",
    "Iitin": "Kymenlaakso",
    # Etelä-Karjala
    "Lappeenrannan": "Etelä-Karjala",
    "Viipurin": "Etelä-Karjala",
    "Joutsenon": "Etelä-Karjala",
    "Ruokolahden": "Etelä-Karjala",
    "Savitaipaleen": "Etelä-Karjala",
    # Etelä-Savo
    "Mikkelin": "Etelä-Savo",
    "Savonlinnan": "Etelä-Savo",
    "Pieksämäen": "Etelä-Savo",
    "Heinäveden": "Etelä-Savo",
    # Pohjois-Savo
    "Kuopion": "Pohjois-Savo",
    "Iisalmen": "Pohjois-Savo",
    "Varkauden": "Pohjois-Savo",
    "Suonenjoen": "Pohjois-Savo",
    # Pohjois-Karjala
    "Joensuun": "Pohjois-Karjala",
    "Lieksan": "Pohjois-Karjala",
    "Nurmeksen": "Pohjois-Karjala",
    "Kiteen": "Pohjois-Karjala",
    "Tohmajärven": "Pohjois-Karjala",
    # Keski-Suomi
    "Jyväskylän": "Keski-Suomi",
    "Äänekosken": "Keski-Suomi",
    "Jämsän": "Keski-Suomi",
    "Saarijärven": "Keski-Suomi",
    "Viitasaaren": "Keski-Suomi",
    "Laukaan": "Keski-Suomi",
    "Liperin": "Keski-Suomi",
    # Pohjois-Pohjanmaa
    "Oulun": "Pohjois-Pohjanmaa",
    "Oulun laamannikunnan": "Pohjois-Pohjanmaa",
    "Raahen": "Pohjois-Pohjanmaa",
    "Ylivieskan": "Pohjois-Pohjanmaa",
    "Haapajärven": "Pohjois-Pohjanmaa",
    "Kalajoen": "Pohjois-Pohjanmaa",
    "Oulaisten": "Pohjois-Pohjanmaa",
    "Nivalan": "Pohjois-Pohjanmaa",
    "Pyhäjärven": "Pohjois-Pohjanmaa",
    # Lappi
    "Rovaniemen": "Lappi",
    "Kemin": "Lappi",
    "Tornion": "Lappi",
    "Sodankylän": "Lappi",
    # Kainuu
    "Kajaanin": "Kainuu",
    "Sotkamon": "Kainuu",
    "Kuhmon": "Kainuu",
}


ALUEET = {
    "Pohjanmaa": ["pohjanmaa", "österbotten", "vaasan lääni", "vasa län"],
    "Häme": ["häme", "tavastland", "hämeen lääni"],
    "Savo": ["savo", "savolax", "savonlinna", "nyslott"],
    "Varsinais-Suomi": ["varsinais-suomi", "egentliga finland"],
    "Uusimaa": ["uusimaa", "nyland"],
    "Karjala": ["karjala", "karelien", "karelen"],
    "Lappi": ["lappi", "lappland", "lapinmaa"],
    "Satakunta": ["satakunta", "björneborg"],
    "Keski-Suomi": ["keski-suomi", "mellersta finland"],
    "Kymenlaakso": ["kymenlaakso", "kymmene"],
}

# ── Kuntalistat ────────────────────────────────────────────────────────────────
# Muoto: "Näytettävä nimi": [hakusanat tekstistä, min 4 merkkiä]
# Pohjanmaa ja Etelä-Pohjanmaa erittäin kattavasti

# ── Maakunta → aineistokokonaisuuden avainsanat -hakemisto ────────────────────
# Käänteinen AINEISTO_MAAKUNTA: maakunta → lista aineistonimiä joiden alkua matchataan
def hae_maakunnan_aineistot(maakunta):
    """Palauttaa listan aineistokokonaisuuden nimien alusta jotka kuuluvat maakuntaan."""
    return [avain for avain, mk in AINEISTO_MAAKUNTA.items() if mk == maakunta]


# ── Maakunta → täydet aineistonimet (haettu API:sta) ─────────────────────────
MAAKUNTA_AINEISTOT = {
    "Etelä-Pohjanmaa": [
        "Alavuden tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Ilmajoen tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Etelä-Pohjanmaan tuomiokunnan renovoidut tuomiokirjat",
        "Ilmajoen tuomiokunnan renovoidut tuomiokirjat",
        "Alavuden tuomiokunnan renovoidut tuomiokirjat",
    ],
    "Pohjanmaa": [
        "Vaasan hovioikeuden arkisto",
        "Närpiön tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Vaasan raastuvanoikeuden renovoidut tuomiokirjat",
        "Vaasan raastuvanoikeuden arkisto (VMA)",
        "Pohjanmaan itäisen tuomiokunnan renovoidut tuomiokirjat",
        "Pohjanmaan pohjoisen tuomiokunnan renovoidut tuomiokirjat",
        "Kristiinankaupungin raastuvanoikeuden renovoidut tuomiokirjat",
        "Kaskisten raastuvanoikeuden renovoidut tuomiokirjat",
        "Vaasan laamannikunnan renovoidut tuomiokirjat",
        "Vaasan ja Oulun laamannikunnan renovoidut tuomiokirjat",
        "Kaskisten raastuvanoikeuden arkisto (VMA)",
        "Vaasan kämnerinoikeuden renovoidut tuomiokirjat",
        "Uudenkaarlepyyn tuomiokunnan renovoidut tuomiokirjat",
        "Närpiön tuomiokunnan renovoidut tuomiokirjat",
        "Uudenkaarlepyyn raastuvanoikeuden renovoidut tuomiokirjat",
        "Pohjanmaan tuomiokunnan renovoidut tuomiokirjat",
    ],
}

def hae_kaikki_maakunnat():
    """Palauttaa uniikit maakunnat aakkosjärjestyksessä."""
    return sorted(set(AINEISTO_MAAKUNTA.values()))


def etsi_paikkakunta_aineistosta(aineistokokonaisuus):
    """Pura paikkakunta ja maakunta aineistokokonaisuuden nimestä."""
    if not aineistokokonaisuus:
        return None, None

    # Irrotetaan ensimmäinen osa ennen "tuomiokunnan", "hovioikeuden" jne.
    erottimet = [
        " tuomiokunnan", " hovioikeuden", " raastuvanoikeuden",
        " laamannikunnan", " alisen ", " ylisen ", " itäisen ", " läntisen "
    ]
    paikkakunta = aineistokokonaisuus
    for erotin in erottimet:
        if erotin in paikkakunta.lower():
            paikkakunta = paikkakunta[:paikkakunta.lower().index(erotin)]
            break

    # Siivotaan sulkeet pois lopusta
    paikkakunta = paikkakunta.split("(")[0].strip()

    # Haetaan maakunta hakemistosta
    maakunta = None
    for avain, mk in AINEISTO_MAAKUNTA.items():
        if paikkakunta.lower().startswith(avain.lower()):
            maakunta = mk
            break

    return paikkakunta if len(paikkakunta) > 2 else None, maakunta

def generoi_tagit(src, indeksi_avain):
    indeksi_avain = tuloksen_indeksi(src, indeksi_avain)
    tagit = []
    teksti_kentta = "transcript" if indeksi_avain == "df" else "teksti"
    teksti = (src.get(teksti_kentta, "") or "").lower()
    aineistokokonaisuus = src.get("aineistokokonaisuus", "") or ""

    # Vuosisatatägi
    try:
        vuosi = int(src.get("alkuvuosi", src.get("dating_start_year", 0)) or 0)
        if vuosi:
            vuosisata = (vuosi // 100) * 100
            tagit.append(f"{vuosisata}-luku")
    except (TypeError, ValueError):
        pass

    # Paikkakunta- ja maakuntätägi aineistokokonaisuudesta
    if indeksi_avain != "df":
        _, maakunta = etsi_paikkakunta_aineistosta(aineistokokonaisuus)
        if maakunta:
            tagit.append(maakunta)
    else:
        # DF: antopaikka
        paikka = src.get("issuingplace", "")
        if paikka:
            tagit.append(paikka)

    # Asiasanatägit (max 2)
    loydetyt = []
    for tagi, hakusanat in ASIASANAT.items():
        if any(s in teksti for s in hakusanat):
            loydetyt.append(tagi)
    tagit.extend(loydetyt[:2])

    if indeksi_avain == "df":
        kieli = src.get("language", "")
        if kieli:
            tagit.append(kieli)

    return tagit[:5]  # max 5 tägiä


def hae_api_avain():
    try:
        return st.secrets["KA_API_KEY"]
    except Exception:
        pass
    return os.environ.get("KA_API_KEY")


# ── Hakulogiikka ──────────────────────────────────────────────────────────────
# Tunnistetaan, onko käyttäjä kirjoittanut omaa hakusyntaksia (lainausmerkit,
# jokerimerkit, AND/OR/NOT, sulkeet). Silloin kysely annetaan sellaisenaan.
_EDISTYNYT_RE = re.compile(r'["*?~()]|\b(AND|OR|NOT)\b')


def on_edistynyt_haku(teksti):
    return bool(teksti and _EDISTYNYT_RE.search(teksti))


def pilko_sanoiksi(teksti):
    """Pilkkoo hakulauseen sanoiksi. Pilkut ja välimerkit toimivat erottimina."""
    if not teksti:
        return []
    return [s for s in re.split(r"[\s,;]+", teksti.strip()) if s]


def sanan_muodot(sana, nimivariaatiot):
    """Palauttaa sanan ja sen historialliset nimimuodot (jos käytössä)."""
    alempi = sana.lower()
    if nimivariaatiot and alempi in NIMIVARIAATIOT:
        return NIMIVARIAATIOT[alempi]
    return [sana]


def sana_lauseke(sana, kentat, nimivariaatiot, sumea):
    """Yksi hakusana: osuma mihin tahansa sen muodoista riittää."""
    lausekkeet = []
    for muoto in sanan_muodot(sana, nimivariaatiot):
        match = {"query": muoto, "fields": kentat}
        if sumea:
            # AUTO: 3–5 merkkiä → 1 virhe, yli 5 merkkiä → 2 virhettä.
            # Ensimmäinen kirjain pidetään kiinni, jotta haku ei leviä liikaa.
            match.update({"fuzziness": "AUTO", "prefix_length": 1, "max_expansions": 50})
        lausekkeet.append({"multi_match": match})
    if len(lausekkeet) == 1:
        return lausekkeet[0]
    return {"bool": {"should": lausekkeet, "minimum_should_match": 1}}


def tekstihaku_lauseke(teksti, kentat, nimivariaatiot, sumea, laaja):
    """
    Rakentaa tekstihaun:
    - Edistynyt syntaksi → query_string sellaisenaan (oletus AND, laajassa OR)
    - Tavallinen haku → jokainen sana omana lausekkeenaan (AND tai laajassa OR)
    """
    if on_edistynyt_haku(teksti):
        return {
            "query_string": {
                "query": teksti,
                "fields": kentat,
                "default_operator": "OR" if laaja else "AND",
                "analyze_wildcard": True,
                "allow_leading_wildcard": False,
            }
        }

    sanat = pilko_sanoiksi(teksti)
    if not sanat:
        return None
    lausekkeet = [sana_lauseke(s, kentat, nimivariaatiot, sumea) for s in sanat]
    if len(lausekkeet) == 1:
        return lausekkeet[0]
    if laaja:
        return {"bool": {"should": lausekkeet, "minimum_should_match": 1}}
    return {"bool": {"must": lausekkeet}}


def laheisyys_boostit(teksti, kentat, nimivariaatiot=False):
    """
    Nostaa kärkeen asiakirjat, joissa sanat ovat peräkkäin tai lähekkäin.
    Ei rajaa tuloksia, vaikuttaa vain järjestykseen.
    Nimivariaatioiden kanssa painotetaan myös esim. "Johan Mäntylä".
    """
    if on_edistynyt_haku(teksti):
        return []
    sanat = pilko_sanoiksi(teksti)
    if len(sanat) < 2:
        return []
    from itertools import islice, product
    muodot = [sanan_muodot(s, nimivariaatiot) for s in sanat]
    lauseet = [" ".join(yhd) for yhd in islice(product(*muodot), 12)]  # enintään 12 yhdistelmää
    boostit = []
    for lause in lauseet:
        boostit.append({"multi_match": {"query": lause, "fields": kentat, "type": "phrase", "boost": 5}})             # täsmälleen peräkkäin
        boostit.append({"multi_match": {"query": lause, "fields": kentat, "type": "phrase", "slop": 5, "boost": 2}})  # enintään ~5 sanan päässä
    return boostit


def kuvaa_haku(hakusana, liittyva_hakusana, nimivariaatiot, sumea, laaja):
    """Selkokielinen kuvaus siitä, mitä haku tekee (näytetään sivupalkissa)."""
    if not hakusana:
        return ""
    if on_edistynyt_haku(hakusana):
        rivit = [f"Oma hakusyntaksi: `{hakusana}`"]
    else:
        osat = []
        for s in pilko_sanoiksi(hakusana):
            muodot = sanan_muodot(s, nimivariaatiot)
            osat.append("(" + " / ".join(muodot) + ")" if len(muodot) > 1 else s)
        liitos = " TAI " if laaja else " JA "
        rivit = [liitos.join(osat)]
    if liittyva_hakusana and liittyva_hakusana.strip():
        rivit.append(f"JA lisäksi: {liittyva_hakusana.strip()}")
    if sumea:
        rivit.append("Sallii pienet kirjoitusvirheet")
    return "  \n".join(rivit)


def rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi, nimivariaatiot, maakunta_filtteri=None, liittyva_hakusana=None, teksti_filtteri_es=None, aineisto_tarkka=None, sumea=False, laaja=False):
    kentat = teksti_kentat(indeksi)
    yhdistelma = on_yhdistelma(indeksi)
    vuosi_kentta_alku = "dating_start_year" if indeksi == "df" else "alkuvuosi"

    # Päähaku: oletuksena kaikkien sanojen täytyy löytyä (AND)
    must = []
    paa = tekstihaku_lauseke(hakusana, kentat, nimivariaatiot, sumea, laaja)
    if paa:
        must.append(paa)

    # Liittyvä hakusana: aina pakollinen (AND päähaun kanssa)
    if liittyva_hakusana and liittyva_hakusana.strip():
        liit = tekstihaku_lauseke(liittyva_hakusana, kentat, nimivariaatiot, sumea, laaja=False)
        if liit:
            must.append(liit)

    # Läheisyys nostaa osuvimmat kärkeen
    should = laheisyys_boostit(hakusana, kentat, nimivariaatiot)

    if yhdistelma:
        # Aineistoilla on eri vuosikentät: kelpuutetaan kumpi tahansa
        aikasuodatin = {"bool": {"should": [
            {"range": {"alkuvuosi": {"gte": vuosi_alku, "lte": vuosi_loppu}}},
            {"range": {"dating_start_year": {"gte": vuosi_alku, "lte": vuosi_loppu}}},
        ], "minimum_should_match": 1}}
    else:
        aikasuodatin = {"range": {vuosi_kentta_alku: {"gte": vuosi_alku, "lte": vuosi_loppu}}}

    # Suodattimet ES-tasolla
    filters = [aikasuodatin]

    # Maakuntasuodatin (rajaa pois DF:n, jolla ei ole maakuntatietoa)
    if maakunta_filtteri and indeksi != "df":
        aineisto_avaimet = hae_maakunnan_aineistot(maakunta_filtteri)
        if aineisto_avaimet:
            maakunta_should = [
                {"prefix": {"aineistokokonaisuus.keyword": {"value": avain}}}
                for avain in aineisto_avaimet
            ]
            filters.append({"bool": {"should": maakunta_should, "minimum_should_match": 1}})

    # Tekstifiltteri ES-tasolla (kohdistuu koko tietokantaan, ei vain ladattuihin)
    if teksti_filtteri_es and teksti_filtteri_es.strip():
        filters.append({
            "query_string": {
                "query": teksti_filtteri_es.strip(),
                "fields": kentat,
                "default_operator": "OR",
                "analyze_wildcard": True
            }
        })

    # Tarkka aineistokokonaisuusfiltteri
    if aineisto_tarkka:
        filters.append({
            "term": {"aineistokokonaisuus.keyword": aineisto_tarkka}
        })

    highlight = {
        "fields": {k: {"fragment_size": 500, "number_of_fragments": 2} for k in kentat},
        "pre_tags": [KOROSTUS_ALKU],
        "post_tags": [KOROSTUS_LOPPU]
    }

    aggs = {
        "vuosittain": {
            "histogram": {"field": vuosi_kentta_alku, "interval": 10, "min_doc_count": 1}
        }
    }
    if yhdistelma and "df" in indeksi.split(","):
        aggs["vuosittain_df"] = {
            "histogram": {"field": "dating_start_year", "interval": 10, "min_doc_count": 1}
        }
    if indeksi != "df":
        aggs["aineistot"] = {
            "terms": {"field": "aineistokokonaisuus.keyword", "size": 50}
        }

    bool_kysely = {"must": must, "filter": filters}
    if should:
        bool_kysely["should"] = should

    return {
        "query": {"bool": bool_kysely},
        "highlight": highlight,
        "aggs": aggs,
        "track_total_hits": True,
        "size": 100,
        "from": 0
    }


@st.cache_data(ttl=3600, show_spinner=False, max_entries=200)
def _hae_es(api_avain, indeksi, kysely_json):
    """Varsinainen rajapintakutsu. Sama haku palautetaan tunnin ajan välimuistista.
    Vain onnistuneet haut tallentuvat, koska virhe keskeyttää funktion."""
    url = f"{ES_URL}/{indeksi}/_search"
    headers = {"Authorization": f"ApiKey {api_avain}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, data=kysely_json.encode("utf-8"), timeout=20)
    resp.raise_for_status()
    return resp.json()


def tee_haku(api_avain, indeksi, kysely):
    kysely_json = json.dumps(kysely, ensure_ascii=False, sort_keys=True)
    try:
        return _hae_es(api_avain, indeksi, kysely_json)
    except requests.exceptions.ConnectionError:
        st.error("Yhteys Kansallisarkiston palvelimeen epäonnistui.")
    except requests.exceptions.Timeout:
        st.error("Haku kesti liian kauan. Kokeile rajata hakua (aikaväli, maakunta).")
    except requests.exceptions.HTTPError as e:
        koodi = e.response.status_code if e.response is not None else "?"
        if koodi == 401:
            st.error("API-avain virheellinen tai puuttuu.")
        elif koodi == 403:
            st.error("Ei käyttöoikeutta tähän aineistoon. Kokeile valita aineisto erikseen.")
        else:
            st.error(f"API-virhe {koodi}")
    except Exception as e:
        st.error(f"Virhe: {type(e).__name__}")
    return None


PAAVARI = "#4b4038"  # sama kuin teeman primaryColor (.streamlit/config.toml)


def muotoile_luku(n):
    """3770 → '3 770' (suomalainen tuhaterotin, sitova välilyönti)."""
    return f"{n:,}".replace(",", " ")


def vuosikymmenjakauma(resp):
    """Vuosikymmen → osumamäärä koko hakutuloksesta (ei vain näytetyistä)."""
    aggregaatit = resp.get("aggregations", {})
    vuosikymmenet = {}
    for nimi in ("vuosittain", "vuosittain_df"):  # yhdistelmähaussa kaksi vuosikenttää
        for b in aggregaatit.get(nimi, {}).get("buckets", []):
            if b["doc_count"] > 0:
                avain = int(b["key"])
                vuosikymmenet[avain] = vuosikymmenet.get(avain, 0) + b["doc_count"]
    return vuosikymmenet


def _tyyli_kaavio(fig, korkeus=None):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False, margin=dict(l=8, r=8, t=48, b=8),
        font=dict(size=14),
    )
    if korkeus:
        fig.update_layout(height=korkeus)
    return fig


def nayta_visualisoinnit(resp):
    vuosikymmenet = vuosikymmenjakauma(resp)
    if vuosikymmenet:
        df_aika = pd.DataFrame([
            {"Vuosikymmen": k, "Osumia": n} for k, n in sorted(vuosikymmenet.items())
        ])
        fig = px.bar(df_aika, x="Vuosikymmen", y="Osumia",
                     title="Osumat vuosikymmenittäin",
                     color_discrete_sequence=[PAAVARI])
        st.plotly_chart(_tyyli_kaavio(fig), width="stretch")

    agg_aineistot = resp.get("aggregations", {}).get("aineistot", {}).get("buckets", [])
    if agg_aineistot:
        maakunta_laskuri = {}
        for b in agg_aineistot:
            _, maakunta = etsi_paikkakunta_aineistosta(b["key"])
            avain = maakunta or "Muu tai tuntematon"
            maakunta_laskuri[avain] = maakunta_laskuri.get(avain, 0) + b["doc_count"]

        if maakunta_laskuri:
            df_mk = pd.DataFrame([
                {"Maakunta": mk, "Osumia": n} for mk, n in maakunta_laskuri.items()
            ]).sort_values("Osumia", ascending=True)
            fig_mk = px.bar(df_mk, x="Osumia", y="Maakunta", orientation="h",
                            title="Osumat maakunnittain",
                            color_discrete_sequence=[PAAVARI])
            st.plotly_chart(_tyyli_kaavio(fig_mk, max(300, len(maakunta_laskuri) * 36)),
                            width="stretch")

        df_a = pd.DataFrame([
            {"Aineisto": b["key"], "Osumia": b["doc_count"]} for b in agg_aineistot
        ]).sort_values("Osumia", ascending=True)
        fig2 = px.bar(df_a, x="Osumia", y="Aineisto", orientation="h",
                      title="Osumat aineistokokonaisuuksittain",
                      color_discrete_sequence=["#b7863a"])
        st.plotly_chart(_tyyli_kaavio(fig2, max(300, len(agg_aineistot) * 32)),
                        width="stretch")


def hae_gemini_avain():
    """Hae Gemini API-avain ympäristömuuttujista tai Streamlit secretseistä."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


# Mallit järjestyksessä. Ilmaistason päiväraja (RPD) projektilla 11/2026:
#   gemini-3.5-flash-lite 500/pv, gemini-3.1-flash-lite 500/pv, gemini-2.5-flash-lite 20/pv.
# Rajat ovat mallikohtaisia, joten jos yksi on täynnä (429) tai poistunut käytöstä (404),
# kokeillaan seuraavaa. Rajat näkee AI Studiosta: Rate Limit -sivu.
GEMINI_MALLIT = [
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
]

SELITYS_VERSIO = 3  # nosta, kun ohje muuttuu: vanhat välimuistissa olevat selitykset vaihtuvat uusiin
SELITYS_PROMPT = """Olet sukututkimukseen perehtynyt arkistoasiantuntija. Selität Kansallisarkiston historiallisia asiakirjoja selkeällä suomen yleiskielellä harrastajasukututkijalle.

Huomaa: teksti on koneellisesti tunnistettua (OCR). Siinä on lukuvirheitä, sanoja on katkennut rivinvaihdoissa (merkki ¬) ja osa tekstistä on ruotsia tai vanhaa suomea. Älä keksi tietoja. Jos nimi, luku tai päivämäärä on epävarma, merkitse se kysymysmerkillä suluissa (?). Jos tekstistä on jätetty pois keskiosa, se on merkitty […].

Vastaa täsmälleen alla olevassa muodossa: jokainen osio alkaa omalla rivillään lihavoidulla otsikolla, ja listat merkitään viivalla. Älä kirjoita mitään ennen ensimmäistä otsikkoa. Jätä osio kokonaan pois (myös otsikko), jos asiakirjassa ei ole sille tietoa.

**Mistä on kyse**
3–5 lausetta. Kerro, millainen asia oli käsittelyssä ja miksi, mitä päätettiin tai sovittiin ja mitä se tarkoitti osapuolille.

**Henkilöt**
- Nimi: rooli, sukulaisuus muihin ja sääty tai ammatti (esim. talollinen, torppari, leski, lautamies), jos ne kerrotaan. Luettele vain asian kannalta olennaiset henkilöt; todistajat voi koota yhdelle riville.

**Tapahtumapaikka**
Kylä, pitäjä ja talo. Enintään 1 lause.

**Sukututkijalle**
- Tiedot, jotka kannattaa kirjata sukututkimukseen: päivämäärät (syntymä, kuolema, vihkiminen, kauppa, käräjäpäivä), sukulaisuussuhteet, talon nimi ja numero, kylä ja maaosuudet. Yksi tieto per rivi. Kirjoita nimet ja päivämäärät niin kuin ne asiakirjassa lukevat.

**Vanhat sanat**
- sana: lyhyt selitys (enintään 4 vanhaa termiä tai ruotsinkielistä sanaa, esim. manttaali, puumerkki, lainhuuto)

**Historiallinen tausta**
Enintään 2 lausetta, ja vain jos yhteys asiakirjaan on selvä.

Asiakirja:
{katkelma}"""


KIINTIO_LOPPU = "kiintio_loppu"


@st.cache_resource
def _kiintion_tila():
    """Palvelimen yhteinen tila: näkyy kaikille käyttäjille (sinä ja isä) samaan aikaan."""
    return {"estetty_asti": None}


def kiintio_estetty_asti():
    """Palauttaa ajan (Helsingin aikaa), jolloin selitykset palaavat, tai None jos käytössä."""
    asti = _kiintion_tila()["estetty_asti"]
    if asti and datetime.now(timezone.utc) < asti:
        return (asti - timedelta(minutes=2)).astimezone(ZoneInfo("Europe/Helsinki"))  # näytetään tasatunti
    return None


def merkitse_kiintio_loppuneeksi():
    """Googlen päiväkiintiö nollautuu keskiyöllä Tyynenmeren aikaa (Suomessa klo 10 tai 9 kesäaikojen erotessa).
    Estetään toiminto siihen asti, ettei turhia pyyntöjä lähetetä."""
    nyt_la = datetime.now(ZoneInfo("America/Los_Angeles"))
    keskiyo = (nyt_la + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    _kiintion_tila()["estetty_asti"] = keskiyo.astimezone(timezone.utc) + timedelta(minutes=2)


class GeminiVirhe(Exception):
    def __init__(self, koodi, viesti):
        super().__init__(viesti)
        self.koodi = koodi


@st.cache_data(ttl=60 * 60 * 24 * 30, max_entries=1000, show_spinner=False)
def _selitys_valimuistista(katkelma, versio, _avain):
    """Sama asiakirja selitetään vain kerran: tulos jaetaan kaikille käyttäjille 30 päiväksi.
    Vain onnistuneet selitykset tallentuvat, koska virhe keskeyttää funktion.
    Alaviivalla alkavaa avainta ei käytetä välimuistin tunnisteena."""
    payload = {
        "contents": [{"parts": [{"text": SELITYS_PROMPT.format(katkelma=katkelma)}]}],
        # Gemini 3.x -mallit toimivat parhaiten oletuslämpötilalla; Flash-Lite ajattelee oletuksena minimaalisesti.
        "generationConfig": {"maxOutputTokens": 1800},
    }
    viimeisin = None
    paivaraja_tayttyi = 0
    for malli, nimi in GEMINI_MALLIT:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{malli}:generateContent"
        try:
            resp = requests.post(url, headers={"x-goog-api-key": _avain, "Content-Type": "application/json"},
                                 json=payload, timeout=30)
        except requests.exceptions.RequestException as e:
            raise GeminiVirhe(0, f"Yhteys tekoälypalveluun epäonnistui ({type(e).__name__}).")
        if resp.status_code in (404, 429, 503):
            viimeisin = resp.status_code  # malli täynnä, ylikuormittunut tai poistunut: kokeillaan seuraavaa
            if resp.status_code == 429 and "PerDay" in resp.text:
                paivaraja_tayttyi += 1
            continue
        if resp.status_code in (400, 401, 403):
            raise GeminiVirhe(resp.status_code, "Gemini API-avain virheellinen. Tarkista GEMINI_API_KEY.")
        if not resp.ok:
            raise GeminiVirhe(resp.status_code, f"Tekoälypalvelun virhe {resp.status_code}.")
        osat = (resp.json().get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        teksti = "".join(o.get("text", "") for o in osat if not o.get("thought")).strip()
        if not teksti:
            raise GeminiVirhe(200, "Tekoäly palautti tyhjän vastauksen tai sisältö suodatettiin.")
        return teksti, nimi
    if viimeisin == 429 and paivaraja_tayttyi:
        raise GeminiVirhe(KIINTIO_LOPPU, "Päivän ilmaiset tekoälyselitykset on käytetty.")
    if viimeisin == 429:
        raise GeminiVirhe(429, "Tekoälyltä pyydettiin juuri liian monta selitystä. Odota minuutti ja yritä uudelleen.")
    raise GeminiVirhe(viimeisin or 0, "Tekoälypalvelu ei juuri nyt vastaa. Yritä hetken päästä uudelleen.")


def selita_asiakirja_geminilla(asiakirja_teksti: str):
    """Palauttaa (selitys, mallin nimi) tai (virheviesti, None)."""
    gemini_avain = hae_gemini_avain()
    if not gemini_avain:
        return "Gemini API-avain puuttuu. Lisää GEMINI_API_KEY Streamlitin Secrets-asetuksiin.", None
    # Normalisoidaan välilyönnit, jotta sama asiakirja osuu välimuistiin.
    # Pitkästä tekstistä otetaan alku ja loppu, koska päätös on pöytäkirjoissa usein lopussa.
    teksti = " ".join(asiakirja_teksti.split())
    katkelma = teksti if len(teksti) <= 8000 else teksti[:6000] + " […] " + teksti[-2000:]
    try:
        return _selitys_valimuistista(katkelma, SELITYS_VERSIO, gemini_avain)
    except GeminiVirhe as e:
        if e.koodi == KIINTIO_LOPPU:
            merkitse_kiintio_loppuneeksi()
        return str(e), None


def turvallinen_katkelma(teksti):
    """Escapataan asiakirjan teksti ja muutetaan ES:n korostusmerkit <mark>-tageiksi."""
    teksti = html.escape(teksti or "")
    return (teksti.replace(KOROSTUS_ALKU, "<mark>")
                  .replace(KOROSTUS_LOPPU, "</mark>")
                  .replace("\n", "<br>"))


def tuloksen_vuosi(src):
    alku = src.get("alkuvuosi", src.get("dating_start_year"))
    loppu = src.get("loppuvuosi", src.get("dating_end_year"))
    if alku in (None, "") and loppu in (None, ""):
        return "Vuosi ei tiedossa"
    if loppu in (None, "") or str(loppu) == str(alku):
        return str(alku)
    return f"{alku}–{loppu}"


ASIASANATAGIT = set(ASIASANAT.keys()) - {"Henkilö"}  # liian yleinen näytettäväksi


# ── Suosikit: tallennetaan selaimen omaan muistiin (localStorage) ─────────────
# Jokaisella selaimella on oma listansa, joten sinulla ja isälläsi on automaattisesti omat suosikit.
# Komponentti lukee listan kerran istunnon alussa ja kirjoittaa sen aina, kun versio kasvaa.
SUOSIKIT_JS = """
export default function(component) {
  const { data, setStateValue } = component;
  const AVAIN = 'kansallisarkisto_haku_suosikit_v1';
  window.__kahSuosikit = window.__kahSuosikit || {};
  const tila = window.__kahSuosikit;
  if (!data || !data.tunnus) return;
  if (tila.tunnus !== data.tunnus) { tila.tunnus = data.tunnus; tila.versio = 0; tila.luettu = false; }
  if (data.versio > tila.versio) {
    try { localStorage.setItem(AVAIN, data.kirjoita); } catch (e) {}
    tila.versio = data.versio;
  }
  if (!tila.luettu) {
    tila.luettu = true;
    let raaka = null;
    try { raaka = localStorage.getItem(AVAIN); } catch (e) {}
    setStateValue('arvo', raaka === null ? '[]' : raaka);
  }
}
"""
_suosikkivarasto = st.components.v2.component("kah_suosikkivarasto", js=SUOSIKIT_JS)

SUOSIKIN_KENTAT = ["aineistokokonaisuus", "arkistoyksikkö", "pääsarja", "alkuvuosi", "loppuvuosi",
                   "dating_start_year", "dating_end_year", "url", "issuingplace", "issuingplacecountry",
                   "language", "df", "indexterm", "teksti", "transcript"]


def synkronoi_suosikit():
    """Kutsutaan kerran jokaisella ajolla ennen tulosten piirtämistä."""
    st.session_state.setdefault("suosikit_tunnus", uuid.uuid4().hex)
    st.session_state.setdefault("suosikit_versio", 0)
    st.session_state.setdefault("suosikit", None)
    lista = st.session_state["suosikit"]
    tulos = _suosikkivarasto(
        key="suosikkivarasto",
        data={"tunnus": st.session_state["suosikit_tunnus"], "versio": st.session_state["suosikit_versio"],
              "kirjoita": json.dumps(lista or [], ensure_ascii=False)},
        default={"arvo": None}, on_arvo_change=lambda: None, height=0)
    if lista is None and tulos.arvo is not None:
        try:
            ladattu = json.loads(tulos.arvo)
            st.session_state["suosikit"] = ladattu if isinstance(ladattu, list) else []
        except (ValueError, TypeError):
            st.session_state["suosikit"] = []


def _tallenna_suosikit(lista):
    st.session_state["suosikit"] = lista
    st.session_state["suosikit_versio"] += 1


def on_suosikki(tunnus):
    return any(s.get("id") == tunnus for s in (st.session_state.get("suosikit") or []))


def _vaihda_suosikki(tulos, indeksi_avain, hakusana):
    lista = list(st.session_state.get("suosikit") or [])
    tunnus = tulos.get("_id", "")
    if on_suosikki(tunnus):
        lista = [s for s in lista if s.get("id") != tunnus]
    else:
        src = tulos.get("_source", {})
        tallennettava = {k: src[k] for k in SUOSIKIN_KENTAT if src.get(k) not in (None, "")}
        for k in ("teksti", "transcript"):
            if k in tallennettava:
                tallennettava[k] = str(tallennettava[k])[:15000]
        korostus = {k: v[:1] for k, v in (tulos.get("highlight") or {}).items()}
        lista.insert(0, {"id": tunnus, "indeksi": indeksi_avain, "source": tallennettava,
                         "highlight": korostus, "hakusana": hakusana or "",
                         "lisatty": datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%d.%m.%Y"),
                         "muistiinpano": ""})
    _tallenna_suosikit(lista)


def _paivita_muistiinpano(tunnus, avain):
    lista = list(st.session_state.get("suosikit") or [])
    for s in lista:
        if s.get("id") == tunnus:
            s["muistiinpano"] = st.session_state.get(avain, "")
    _tallenna_suosikit(lista)


def nayta_tulos(tulos, idx, indeksi_avain, suosikki=None):
    src = tulos.get("_source", {})
    highlights = tulos.get("highlight", {})
    indeksi_avain = tuloksen_indeksi(src, indeksi_avain)
    url = src.get("url", "")

    if indeksi_avain == "df":
        paikka = src.get("issuingplace", "")
        lahde = src.get("df", src.get("indexterm", "Diplomatarium Fennicum"))
        teksti_kentta = "transcript"
    else:
        _, maakunta = etsi_paikkakunta_aineistosta(src.get("aineistokokonaisuus", ""))
        paikka = maakunta or ""
        osat = [src.get("aineistokokonaisuus", ""), src.get("arkistoyksikkö", "")]
        lahde = " · ".join(o for o in osat if o)
        teksti_kentta = "teksti"

    # Kärkeen se, mitä sukututkija etsii ensin: vuosi ja paikka. Lähde toissijaisena.
    otsikko = f"<span class='tulos-vuosi'>{html.escape(tuloksen_vuosi(src))}</span>"
    if paikka:
        otsikko += f"<span class='tulos-paikka'> · {html.escape(paikka)}</span>"
    linkki = (f"<a class='tulos-linkki' href='{html.escape(url, quote=True)}' target='_blank' "
              f"rel='noopener'>Avaa alkuperäinen asiakirja (Astia)</a>") if url else ""

    aiheet = [t for t in generoi_tagit(src, indeksi_avain) if t in ASIASANATAGIT]
    tagirivi = "".join(f"<span class='tagi'>{html.escape(t)}</span>" for t in aiheet)

    katkelmat = highlights.get(teksti_kentta, [])
    if katkelmat:
        katkelma = turvallinen_katkelma(katkelmat[0])
    else:
        teksti = src.get(teksti_kentta, "") or ""
        katkelma = turvallinen_katkelma(teksti[:300] + ("…" if len(teksti) > 300 else ""))

    # Yläreuna: vuosi ja paikka vasemmalla, Astia-linkki ja oikeassa kulmassa suosikki
    tunnus = tulos.get("_id", "")
    with st.container(horizontal=True, vertical_alignment="center", gap="small",
                      key=f"kortinyla_{idx}_{tunnus}"):
        st.markdown(f"<div class='tulos-nimi'>{otsikko}</div>", unsafe_allow_html=True, width="stretch")
        if linkki:
            st.markdown(linkki, unsafe_allow_html=True, width="content")
        if st.session_state.get("suosikit") is not None and tunnus:
            tallennettu = on_suosikki(tunnus)
            st.button("Tallennettu" if tallennettu else "Tallenna suosikiksi",
                      key=f"suosikki_{'on' if tallennettu else 'ei'}_{idx}_{tunnus}", type="tertiary",
                      icon=":material/bookmark_added:" if tallennettu else ":material/bookmark_add:",
                      help="Poista suosikeista" if tallennettu else "Tallenna tämä asiakirja Suosikit-välilehdelle",
                      on_click=_vaihda_suosikki,
                      args=(tulos, indeksi_avain, (st.session_state.get("hakutulos") or {}).get("hakusana", "")))

    st.markdown(
        f"<div class='tulos'>"
        f"<div class='tulos-lahde'>{html.escape(lahde)}</div>"
        + (f"<div class='tagirivi'>{tagirivi}</div>" if tagirivi else "")
        + (f"<div class='katkelma'>{katkelma}</div>" if katkelma else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    if suosikki is not None:
        if suosikki.get("hakusana") or suosikki.get("lisatty"):
            st.caption(f"Tallennettu {suosikki.get('lisatty', '')}"
                       + (f" haulla ”{suosikki['hakusana']}”" if suosikki.get("hakusana") else ""))
        avain = f"muistiinpano_{tunnus}"
        st.session_state.setdefault(avain, suosikki.get("muistiinpano", ""))
        st.text_input("Oma muistiinpano", key=avain, placeholder="esim. isoisän isä? tarkista rippikirjasta",
                      on_change=_paivita_muistiinpano, args=(tunnus, avain))

    koko_teksti = src.get(teksti_kentta, "") or ""
    if koko_teksti:
        nayta_selityslaatikko(tulos, idx, koko_teksti)

    with st.expander("Koko teksti ja lähdetiedot", expanded=False):
        if indeksi_avain != "df":
            tiedot = [("Aineisto", src.get("aineistokokonaisuus")), ("Pääsarja", src.get("pääsarja")),
                      ("Arkistoyksikkö", src.get("arkistoyksikkö"))]
        else:
            maa = src.get("issuingplacecountry")
            paikka = src.get("issuingplace") or "–"
            tiedot = [("Antopaikka", f"{paikka} ({maa})" if maa else paikka), ("Kieli", src.get("language"))]
        st.markdown("<dl class='lisatiedot'>" + "".join(
            f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v or '–'))}</dd>" for k, v in tiedot)
            + "</dl>", unsafe_allow_html=True)
        if koko_teksti:
            st.markdown(f"<div class='koko-teksti'>{turvallinen_katkelma(koko_teksti)}</div>",
                        unsafe_allow_html=True)


def nayta_selityslaatikko(tulos, idx, koko_teksti):
    """Meripihkainen laatikko jokaisessa tuloskortissa: kutsu tekoälyselitykseen ja selitys itse."""
    selitys_avain = f"selitys_{idx}_{tulos.get('_id', '')}"
    with st.container(key=f"selityslaatikko_{selitys_avain}"):
        valmis = st.session_state.get(selitys_avain)
        if valmis and valmis[1]:
            selitys, malli = valmis
            st.markdown("<div class='selitys-otsikko'>Mitä tässä sanotaan?</div>", unsafe_allow_html=True)
            # Pelkän lihavoidun otsikon riville rivinvaihto, jotta otsikko ei liimaudu seuraavaan tekstiin
            st.markdown(re.sub(r"(?m)^(\*\*[^*\n]+\*\*):?\s*$", r"\1  ", selitys))
            st.caption(f"Tekoälyn tulkinta ({malli}). Tarkista tärkeät tiedot alkuperäisestä asiakirjasta.")
            return

        palautuu = kiintio_estetty_asti()
        kuvaus = (f"Päivän ilmaiset selitykset on käytetty. Ne palaavat käyttöön {palautuu:%d.%m.} klo {palautuu:%H.%M}."
                  if palautuu else
                  "Tekoäly kertoo selkokielellä, mistä asiakirjassa on kyse ja keitä siinä mainitaan.")
        st.markdown("<div class='selitys-otsikko'>Mitä tässä sanotaan?</div>"
                    f"<div class='selitys-kuvaus'>{kuvaus}</div>", unsafe_allow_html=True)

        if palautuu:
            with st.container(key=f"estetty_{selitys_avain}"):
                st.button("Tekoälyselitykset käytetty tältä päivältä", key=f"btn_{selitys_avain}",
                          icon=":material/block:", disabled=True,
                          help=f"Selitykset palaavat käyttöön {palautuu:%d.%m. klo %H.%M}.")
            return

        paikka = st.empty()
        if paikka.button("Selitä asiakirja", key=f"btn_{selitys_avain}", type="primary",
                         icon=":material/auto_awesome:"):
            paikka.empty()  # painike pois työn ajaksi, ettei sitä paineta uudelleen
            with st.spinner("Tekoäly lukee asiakirjaa ja kirjoittaa selitystä. Tämä kestää yleensä 10–30 sekuntia…",
                            ):
                tulos_ = selita_asiakirja_geminilla(koko_teksti)
            if kiintio_estetty_asti():
                st.rerun()  # kiintiö loppui juuri: päivitetään kaikki napit ja ilmoitus
            if tulos_[1]:
                st.session_state[selitys_avain] = tulos_
                st.rerun()
            st.warning(tulos_[0])


def suodata_ja_jarjesta(tulokset, indeksi_avain, jarjestys, aineisto_filtteri, valitut_tagit, teksti_filtteri=""):

    if aineisto_filtteri and aineisto_filtteri != "Kaikki":
        tulokset = [
            t for t in tulokset
            if t["_source"].get("aineistokokonaisuus", "") == aineisto_filtteri
        ]

    if valitut_tagit:
        def tulos_sisaltaa_tagit(t):
            tuloksen_tagit = generoi_tagit(t["_source"], indeksi_avain)
            return all(tagi in tuloksen_tagit for tagi in valitut_tagit)
        tulokset = [t for t in tulokset if tulos_sisaltaa_tagit(t)]

    if teksti_filtteri and teksti_filtteri.strip():
        haku = teksti_filtteri.strip().lower()
        def sisaltaa(t):
            src = t["_source"]
            teksti = (src.get("teksti") or src.get("transcript") or "").lower()
            return haku in teksti
        tulokset = [t for t in tulokset if sisaltaa(t)]

    def hae_vuosi(t):
        v = t["_source"].get("alkuvuosi", t["_source"].get("dating_start_year"))
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    if jarjestys == "Vanhin ensin":
        tulokset = sorted(tulokset, key=hae_vuosi)
    elif jarjestys == "Uusin ensin":
        tulokset = sorted(tulokset, key=hae_vuosi, reverse=True)

    return tulokset


# ── Ulkoasu ───────────────────────────────────────────────────────────────────
TYYLIT = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1240px; }
[data-testid="stImageCaption"] { font-size: 0.85rem; color: #5f5850; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #5f5850 !important; }
.lisatiedot { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 0 0 14px 0; font-size: 0.95rem; }
.lisatiedot dt { color: #5f5850; font-weight: 700; }
.lisatiedot dd { margin: 0; color: #24211e; }
[data-testid="stImage"] img { border-radius: 8px; }
[data-testid="stAlertContainer"] { background: #ece9e3 !important; color: #24211e !important; }
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] [data-testid="stIconMaterial"] { color: #24211e !important; }
/* Hakukenttä: isompi kuin muut kentät, koska se on sivun pääasia */
div[data-testid="stForm"] input[type="text"] { font-size: 1.15rem; min-height: 3rem; }
div[data-testid="stForm"] { padding: 0; border: none; }
div[data-testid="stForm"] [data-testid="InputInstructions"] { display: none; }

.hero { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); align-items: center; gap: 40px;
  background: #211d1a; border-radius: 14px; min-height: 330px; padding: 0 48px 0 32px; margin-bottom: 1.75rem; overflow: hidden; }
.kollaasi { position: relative; height: 330px; }
.kollaasi img { position: absolute; object-fit: cover; border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.35); outline: 1px solid rgba(255,255,255,0.08); }
.k-perhe { left: 0; top: 40px; width: 54%; height: 180px; object-position: center 45%; }
.k-poika { left: 42%; top: 104px; width: 24%; height: 196px; object-position: center 20%; z-index: 2; }
.k-heina { left: 60%; top: 34px; width: 40%; height: 160px; object-position: center 60%; }
.hero-teksti h1 { margin: 0; padding: 0; color: #fff; font-family: "Atkinson Hyperlegible", sans-serif;
  font-size: clamp(1.6rem, 2.5vw, 2.6rem); font-weight: 700; line-height: 1.12; letter-spacing: -0.015em;
  text-wrap: balance; word-break: keep-all; hyphens: manual; }
.hero-teksti p { margin: 14px 0 0 0; color: #d9d3cb; font-size: 1.05rem; line-height: 1.55; max-width: 46ch; }
.hero-kehys { container-type: inline-size; }
@container (max-width: 600px) {
  .hero { grid-template-columns: 1fr; padding: 28px 24px; min-height: 0; gap: 0; }
  .kollaasi { display: none; }
}

.johdanto { font-size: 1.05rem; line-height: 1.6; max-width: 68ch; color: #3d3832; }

[class*="st-key-tuloskortti_"] { background: #fdfcfa; border: 1px solid #dcd8d0; border-radius: 12px;
  padding: 18px 22px 14px 22px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(36,33,30,0.06), 0 4px 12px rgba(36,33,30,0.04); }
.tulos { padding: 0; }
[class*="st-key-kortinyla_"] { gap: 12px 18px; }
[class*="st-key-kortinyla_"] p { margin: 0; }
.tulos-nimi { line-height: 1.3; }
[class*="st-key-suosikki_on_"] button, [class*="st-key-suosikki_on_"] button p,
[class*="st-key-suosikki_on_"] [data-testid="stIconMaterial"] { color: #8a5a10 !important; font-weight: 700; }
.st-key-muutosilmoitus { background: #f3effd; border: 1.5px solid #a993ea; border-radius: 10px;
  padding: 12px 16px; margin: 4px 0 18px 0; gap: 16px; position: sticky; top: 0.5rem; z-index: 5; }
/* Laventeli: vaalea pohja, Digital Lavender -henkinen reunus ja violetti painike */
.st-key-muutosilmoitus p { color: #2a1d5c; margin: 0; }
.st-key-muutosilmoitus button { background: #5b42bd !important; border-color: #5b42bd !important; color: #fff !important; flex-shrink: 0; }
.st-key-muutosilmoitus button p { color: #fff !important; }
.tulos-otsikko { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; flex-wrap: wrap; }
.tulos-vuosi { font-size: 1.25rem; font-weight: 700; color: #24211e; font-variant-numeric: tabular-nums; }
.tulos-paikka { font-size: 1.1rem; color: #24211e; }
.tulos-linkki { font-size: 0.95rem; white-space: nowrap; color: #4b4038 !important; text-underline-offset: 3px; }
.tulos-lahde { font-size: 0.9rem; color: #5f5850; margin-top: -6px; }
.tagirivi { margin-top: 8px; }
.rajausrivi { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 2px 0 6px 0; }
.rajaus-otsikko { font-size: 0.9rem; color: #5f5850; font-weight: 700; margin-right: 4px; }
.rajaus { display: inline-block; padding: 3px 12px; border-radius: 999px; background: #e3ded5;
  color: #24211e; font-size: 0.9rem; border: 1px solid #d3cdc2; }
[data-testid="stHeaderActionElements"] { display: none; }
.kiintio-ilmoitus { background: #fbe9e7; border: 1px solid #efb7ae; color: #7a1d12; border-radius: 8px;
  padding: 12px 16px; margin: -0.5rem 0 1.25rem 0; line-height: 1.5; }
[class*="st-key-estetty_"] button, [class*="st-key-estetty_"] button:disabled { background: #b42318 !important;
  border-color: #b42318 !important; color: #fff !important; opacity: 1 !important; cursor: not-allowed; }
[class*="st-key-estetty_"] button p, [class*="st-key-estetty_"] button span { color: #fff !important; }
.tagi { display: inline-block; padding: 2px 10px; margin: 0 6px 4px 0; border-radius: 999px;
  background: #f3e6c8; color: #6e4c12; font-size: 0.85rem; }
.katkelma { background: #ece9e3; padding: 10px 14px; border-radius: 6px; margin-top: 10px;
  font-size: 0.98rem; line-height: 1.6; color: #2f2b27; max-width: 80ch; }
.katkelma mark, .koko-teksti mark { background: #f6d58e; color: inherit; padding: 0 2px; border-radius: 2px; }
[class*="st-key-selityslaatikko_"] { background: #fbf1dc; border: 1px solid #ecd6a6; border-radius: 10px;
  padding: 14px 18px; margin: 10px 0 8px 0; max-width: 80ch; gap: 0.5rem; }
.selitys-otsikko { font-weight: 700; color: #6e4c12; font-size: 1.05rem; margin-bottom: 6px; }
.selitys-kuvaus { color: #5a4a33; font-size: 0.95rem; margin: -2px 0 8px 0; }
[class*="st-key-selityslaatikko_"] [data-testid="stCaptionContainer"] p { color: #6b5a3e !important; }
[class*="st-key-selityslaatikko_"] [data-testid="stSpinner"] { color: #6e4c12; font-weight: 700; }
[class*="st-key-selityslaatikko_"] [data-testid="stSpinner"] i { border-color: #ecd6a6; border-top-color: #b7863a; }
.koko-teksti { font-size: 0.95rem; line-height: 1.7; color: #2f2b27; max-height: 420px; overflow-y: auto; }
::selection { background: #f6d58e; color: #24211e; }
</style>
"""

# Lähdetiedot. Museovirasto pyytää mainitsemaan lähteen myös Public Domain -kuvissa.
KUVALAHTEET = [
    ("Kyrönjoen Ritaalankosken oikea haara, Isokyrö, 1912",
     "Museovirasto, Historian kuvakokoelma, HK8134:3316. Public Domain.",
     "https://museovirasto.finna.fi/Record/museovirasto.6bbfffc5-e4b2-49ca-8a35-d514a443cca8"),
    ("Perhe talon edustalla Uudenkaarlepyyn seudulla, 1900–1906",
     "Kuvaaja J. W. Schalin. Museovirasto, Historian kuvakokoelma, HK10019:53. Public Domain.",
     "https://museovirasto.finna.fi/Record/museovirasto.622f951c-eb53-4b99-bae0-c47309543d79"),
]

ESIMERKKIHAUT = ["Mäntylä", "Juho Mäntylä", "Mänty*"]


def _aseta_ja_hae(**arvot):
    """Painikkeiden callback: asettaa kenttien arvot ja käynnistää haun."""
    for avain, arvo in arvot.items():
        st.session_state[avain] = arvo
    st.session_state["aja_haku"] = True


def nayta_nollatulos(haku):
    hakusana = haku["hakusana"]
    st.markdown(f"#### Haulla ”{hakusana}” ei löytynyt asiakirjoja")
    st.markdown("Vanhat asiakirjat on kirjoitettu käsin ja usein ruotsiksi, joten sama nimi voi "
                "esiintyä monessa muodossa. Kokeile jotakin näistä:")

    ehdotukset = []
    sanat = pilko_sanoiksi(hakusana)
    edistynyt = on_edistynyt_haku(hakusana)
    if not st.session_state.get("nimivariaatiot") and any(s.lower() in NIMIVARIAATIOT for s in sanat):
        ehdotukset.append(("Hae myös etunimen vanhoilla muodoilla", {"nimivariaatiot": True}))
    if not st.session_state.get("sumea") and not edistynyt:
        ehdotukset.append(("Salli pienet kirjoitusvirheet", {"sumea": True}))
    if len(sanat) == 1 and not edistynyt and len(sanat[0]) >= 5:
        alku = sanat[0][:-2] + "*"
        ehdotukset.append((f"Hae sanan alulla {alku}", {"hakusana": alku}))
    if len(sanat) > 1 and not edistynyt and not st.session_state.get("laaja"):
        ehdotukset.append(("Riittää, että yksi sanoista löytyy", {"laaja": True}))

    if ehdotukset:
        sarakkeet = st.columns(len(ehdotukset))
        for sarake, (teksti, arvot) in zip(sarakkeet, ehdotukset):
            sarake.button(teksti, on_click=_aseta_ja_hae, kwargs=arvot, width="stretch")
    st.caption("Voit myös laajentaa aikaväliä tai poistaa maakuntarajauksen sivupalkin "
               "Tarkenna hakua -osiosta. Paikannimet kannattaa kokeilla ruotsiksi, esim. Ilmajoki → Ilmola, Vaasa → Wasa.")


def nayta_tulokset(haku):
    tulokset_raw = haku["tulokset"]
    resp = haku["resp"]
    indeksi = haku["indeksi_avain"]
    osumia = haku["osumia"]

    st.markdown(f"### Tulokset haulle ”{haku['hakusana']}”")
    yhteenveto = [f"{muotoile_luku(osumia)} asiakirjaa"]
    if osumia > len(tulokset_raw):
        yhteenveto.append(f"näytetään {len(tulokset_raw)} osuvinta")
    vk = vuosikymmenjakauma(resp)
    if vk:
        yhteenveto.append(f"vuosilta {min(vk)}–{max(vk) + 9}")
    st.markdown(" · ".join(yhteenveto))
    rajaukset = [haku.get("aineisto_nimi")] + haku.get("rajaukset", [])
    st.markdown("<div class='rajausrivi'><span class='rajaus-otsikko'>Rajaukset</span>"
                + "".join(f"<span class='rajaus'>{html.escape(r)}</span>" for r in rajaukset if r)
                + "</div>", unsafe_allow_html=True)
    if haku.get("kuvaus"):
        st.caption(f"Hakuehto: {haku['kuvaus']}")

    # Rajaus ilman uutta hakua
    with st.expander("Järjestä ja rajaa tuloksia", expanded=False, icon=":material/tune:"):
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            jarjestys = st.selectbox("Järjestys", ["Osuvin ensin", "Vanhin ensin", "Uusin ensin"])
        with fcol2:
            aineistot = sorted({t["_source"].get("aineistokokonaisuus", "")
                                for t in tulokset_raw if t["_source"].get("aineistokokonaisuus")})
            if aineistot and indeksi != "df":
                aineisto_filtteri = st.selectbox("Aineistokokonaisuus", ["Kaikki"] + aineistot)
            else:
                aineisto_filtteri = "Kaikki"
        with fcol3:
            teksti_filtteri = st.text_input("Etsi näistä tuloksista", placeholder="esim. perintö, torppari")
        kaikki_tagit = sorted({tagi for t in tulokset_raw
                               for tagi in generoi_tagit(t["_source"], indeksi)})
        valitut_tagit = st.multiselect("Aihe, maakunta tai vuosisata", options=kaikki_tagit,
                                       placeholder="Valitse yksi tai useampi")

    tulokset = suodata_ja_jarjesta(tulokset_raw, indeksi, jarjestys, aineisto_filtteri,
                                   valitut_tagit, teksti_filtteri)
    if len(tulokset) != len(tulokset_raw):
        st.caption(f"Rajauksen jälkeen {len(tulokset)} / {len(tulokset_raw)} tulosta.")

    if not tulokset:
        st.info("Rajaus jätti tulokset tyhjiksi. Poista jokin rajaus yllä.")
    else:
        for idx, tulos in enumerate(tulokset):
            with st.container(key=f"tuloskortti_{idx}_{tulos.get('_id', '')}"):
                nayta_tulos(tulos, idx, indeksi)

    st.divider()
    with st.expander("Osumien jakaumat (vuosikymmenet, maakunnat, aineistot)", icon=":material/bar_chart:"):
        nayta_visualisoinnit(resp)

    if st.query_params.get("debug") == "1" and haku.get("kysely"):
        with st.expander("Lähetetty kysely (kehittäjille)"):
            st.json(haku["kysely"])


def nayta_suosikit():
    lista = st.session_state.get("suosikit")
    if lista is None:
        st.caption("Ladataan suosikkeja…")
        return
    if not lista:
        st.markdown("<p class='johdanto'>Et ole vielä tallentanut suosikkeja. Paina hakutuloksessa "
                    "<b>Tallenna suosikiksi</b>, niin asiakirja tallentuu tänne. Voit lisätä siihen myös "
                    "oman muistiinpanon.</p>", unsafe_allow_html=True)
    else:
        st.markdown(f"### Suosikit ({len(lista)})")
        st.caption("Suosikit tallentuvat tämän selaimen muistiin. Toisella laitteella tai selaimella on oma listansa.")
        for i, s in enumerate(lista):
            tulos = {"_id": s.get("id", ""), "_source": s.get("source", {}), "highlight": s.get("highlight", {})}
            with st.container(key=f"tuloskortti_s{i}_{s.get('id', '')}"):
                nayta_tulos(tulos, f"s{i}", s.get("indeksi", "tuomiokirjat"), suosikki=s)

    with st.expander("Varmuuskopio", icon=":material/save:"):
        st.caption("Suosikit katoavat, jos selaimen tiedot tyhjennetään. Lataa varmuuskopio talteen, "
                   "niin voit palauttaa ne myöhemmin tai siirtää toiselle laitteelle.")
        st.download_button("Lataa suosikit tiedostona", icon=":material/download:",
                           data=json.dumps(lista or [], ensure_ascii=False, indent=1),
                           file_name="kansallisarkisto-suosikit.json", mime="application/json",
                           disabled=not lista)
        tiedosto = st.file_uploader("Palauta suosikit tiedostosta", type=["json"], key="suosikit_palautus")
        if tiedosto is not None and st.button("Lisää tiedoston suosikit", icon=":material/upload:"):
            try:
                tuodut = json.loads(tiedosto.getvalue().decode("utf-8"))
                olemassa = {s.get("id") for s in (lista or [])}
                uudet = [t for t in tuodut if isinstance(t, dict) and t.get("id") and t.get("id") not in olemassa]
                _tallenna_suosikit(uudet + list(lista or []))
                st.success(f"Lisättiin {len(uudet)} suosikkia.")
                st.rerun()
            except (ValueError, UnicodeDecodeError):
                st.error("Tiedostoa ei voitu lukea. Valitse aiemmin ladattu suosikkitiedosto.")


def main():
    st.set_page_config(
        page_title="Kansallisarkiston Sisältöhaku – sukututkimus",
        page_icon=":material/history_edu:",
        layout="wide",
        initial_sidebar_state="auto",
    )
    st.markdown(TYYLIT, unsafe_allow_html=True)

    # Oletusarvot ennen widgettejä, jotta painikkeet voivat muuttaa niitä
    for avain, oletus in {"hakusana": "", "nimivariaatiot": True, "sumea": False, "laaja": False}.items():
        st.session_state.setdefault(avain, oletus)

    # ── Banneri ────────────────────────────────────────────────────────────────
    # ── Hero: kuvakollaasi Museoviraston kuvista ───────
    st.markdown("""
        <div class="hero-kehys"><section class="hero" aria-label="Kansallisarkiston Sisältöhaku">
          <div class="kollaasi" aria-hidden="true">
            <img class="k-perhe" src="app/static/kuvat/perhe-uusikaarlepyy.jpg" alt="">
            <img class="k-poika" src="app/static/kuvat/poika-haravoi-hartola.jpg" alt="">
            <img class="k-heina" src="app/static/kuvat/heinanteko.jpg" alt="">
          </div>
          <div class="hero-teksti">
            <h1>Kansallisarkiston Sisältöhaku</h1>
            <p>Etsi esivanhempiasi Kansallisarkiston digitoiduista tuomiokirjoista, voudintileistä ja
               keskiaikaisista asiakirjoista. Tekoäly kertoo selkokielellä, mitä löytämässäsi asiakirjassa sanotaan.</p>
          </div>
        </section></div>
    """, unsafe_allow_html=True)
    palautuu = kiintio_estetty_asti()
    if palautuu:
        st.markdown(
            "<div class='kiintio-ilmoitus' role='status'><strong>Tekoälyselitykset on käytetty tältä päivältä.</strong> "
            f"Ilmainen kiintiö täyttyi, joten toiminto on pois käytöstä {palautuu:%d.%m.} klo {palautuu:%H.%M} asti. "
            "Haku toimii normaalisti.</div>", unsafe_allow_html=True)

    api_avain = hae_api_avain()

    # ── Päähaku: yksi kenttä, Enter hakee ──────────────────────────────────────
    with st.form("haku", border=False, enter_to_submit=True):
        c1, c2, c3 = st.columns([4.4, 3.6, 1.2], vertical_alignment="bottom")
        with c1:
            st.text_input("Hae nimellä, talolla tai paikalla", key="hakusana",
                          placeholder="esim. Mäntylä tai Juho Mäntylä",
                          help="Useampi sana: kaikkien pitää löytyä samasta asiakirjasta. "
                               "Mänty* löytää kaikki Mänty-alkuiset, \"Koivumäen talo\" hakee tarkkaa fraasia, "
                               "Mäntylä OR Männylä riittää jompikumpi.")
        with c2:
            indeksi_nimi = st.selectbox("Aineisto", options=list(INDEKSIT.keys()), index=0, key="aineisto")
        with c3:
            lahetetty = st.form_submit_button("Hae", type="primary", icon=":material/search:",
                                              width="stretch")
    st.caption("Vinkki: 1600–1800-lukujen tuomiokirjat ovat pääosin ruotsiksi. "
               "Kokeile nimiä myös ruotsiksi, esim. Juho → Johan, Ilmajoki → Ilmola.")
    indeksi_avain = INDEKSIT[indeksi_nimi]

    # ── Tarkennettu haku sivupalkissa ──────────────────────────────────────────
    with st.sidebar:
        st.header("Tarkenna hakua")

        if not api_avain:
            api_avain = st.text_input("Kansallisarkiston API-avain", type="password",
                                      help="Avaimen saa Kansallisarkistolta. Katso Ohjeet-välilehti.")

        liittyva_hakusana = st.text_input(
            "Myös tämän sanan pitää löytyä",
            placeholder="esim. Jurva, lautamies",
            help="Asiakirjasta pitää löytyä sekä hakusana että tämä sana.")

        st.subheader("Aikaväli")
        if on_yhdistelma(indeksi_avain):
            vuosi_minimi, vuosi_maksimi = 1100, 1950
        elif indeksi_avain == "voudintilit":
            vuosi_minimi, vuosi_maksimi = 1500, 1634
        elif indeksi_avain == "df":
            vuosi_minimi, vuosi_maksimi = 1100, 1500
        else:
            vuosi_minimi, vuosi_maksimi = 1600, 1950
        col1, col2 = st.columns(2)
        with col1:
            vuosi_alku = st.number_input("Alkaen", min_value=1100, max_value=1980, value=vuosi_minimi, step=10)
        with col2:
            vuosi_loppu = st.number_input("Päättyen", min_value=1100, max_value=1980, value=vuosi_maksimi, step=10)
        if vuosi_alku > vuosi_loppu:
            st.warning("Alkuvuosi on myöhempi kuin loppuvuosi. Haku käyttää vuosia toisin päin.")
            vuosi_alku, vuosi_loppu = vuosi_loppu, vuosi_alku

        kaikki_maakunnat = hae_kaikki_maakunnat()
        maakunta_valinta = st.selectbox(
            "Maakunta", options=["Kaikki"] + kaikki_maakunnat, index=0,
            help="Rajaa haku maakunnan tuomiokirjoihin. Diplomatarium Fennicum jää pois, "
                 "koska siinä ei ole maakuntatietoa.")
        maakunta_filtteri = None if maakunta_valinta == "Kaikki" else maakunta_valinta

        aineisto_tarkka = None
        if maakunta_filtteri and maakunta_filtteri in MAAKUNTA_AINEISTOT:
            aineisto_valinta = st.selectbox(
                "Tuomiokunta tai oikeus", options=["Kaikki"] + MAAKUNTA_AINEISTOT[maakunta_filtteri],
                index=0, help="Rajaa haku yhden tuomiokunnan tai oikeuden aineistoon.")
            aineisto_tarkka = None if aineisto_valinta == "Kaikki" else aineisto_valinta

        st.subheader("Nimet ja kirjoitusasu")
        st.checkbox("Etunimen vanhat muodot", key="nimivariaatiot",
                    help="Hakee etunimelle myös historialliset muodot, esim. Juho → Johan, Johannes.")
        st.checkbox("Salli pienet kirjoitusvirheet", key="sumea",
                    help="Löytää myös esim. Mäntyla tai Mentylä. Tuomiokirjojen teksti on koneellisesti "
                         "tunnistettua käsialaa, joten virheitä on paljon. Tuo myös turhia osumia.")
        st.checkbox("Riittää, että yksi sanoista löytyy", key="laaja",
                    help="Oletuksena kaikkien hakusanojen pitää löytyä samasta asiakirjasta.")

        st.subheader("Aihe")
        teksti_filtteri_es = st.text_input(
            "Asiakirjassa mainitaan jokin näistä",
            placeholder="esim. todistaja, perintö",
            help="Rajaa tuloksiin, joissa esiintyy ainakin yksi näistä sanoista.")
        tulosten_maara = st.slider("Näytettävien tulosten määrä", 10, 500, 100, step=10)

    synkronoi_suosikit()
    tab_haku, tab_suosikit, tab_ohje = st.tabs(["Hakutulokset", "Suosikit", "Ohjeet ja vinkit"])

    with tab_haku:
        hakusana = (st.session_state.get("hakusana") or "").strip()
        aja = lahetetty or st.session_state.pop("aja_haku", False)

        # Sivupalkin rajaukset selkokielellä, jotta tuloksista näkee mitä haettiin
        rajaukset = [f"vuodet {vuosi_alku}–{vuosi_loppu}"]
        if maakunta_filtteri:
            rajaukset.append(maakunta_filtteri)
        if aineisto_tarkka:
            rajaukset.append(aineisto_tarkka)
        if teksti_filtteri_es and teksti_filtteri_es.strip():
            rajaukset.append(f"aihe: {teksti_filtteri_es.strip()}")
        nykyiset_ehdot = (hakusana, indeksi_avain, vuosi_alku, vuosi_loppu, maakunta_filtteri,
                          aineisto_tarkka, (liittyva_hakusana or "").strip(),
                          (teksti_filtteri_es or "").strip(), tulosten_maara,
                          st.session_state["nimivariaatiot"], st.session_state["sumea"],
                          st.session_state["laaja"])

        if aja:
            # Uusi haku korvaa aina edellisen, myös kun osumia ei löydy
            st.session_state.pop("hakutulos", None)
            if not hakusana:
                st.warning("Kirjoita ensin hakusana, esimerkiksi sukunimi tai talon nimi.")
            elif not api_avain:
                st.error("Haku vaatii Kansallisarkiston API-avaimen. Lisää se sivupalkkiin.")
            else:
                nimivariaatiot = st.session_state["nimivariaatiot"]
                sumea = st.session_state["sumea"]
                laaja = st.session_state["laaja"]
                with st.spinner(f"Haetaan ”{hakusana}”…"):
                    kysely = rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi_avain,
                                            nimivariaatiot, maakunta_filtteri, liittyva_hakusana,
                                            teksti_filtteri_es, aineisto_tarkka, sumea=sumea, laaja=laaja)
                    kysely["size"] = tulosten_maara
                    resp = tee_haku(api_avain, indeksi_avain, kysely)
                if resp:
                    st.session_state["hakutulos"] = {
                        "hakusana": hakusana,
                        "kuvaus": kuvaa_haku(hakusana, liittyva_hakusana, nimivariaatiot, sumea, laaja)
                                  .replace("  \n", " · "),
                        "rajaukset": rajaukset,
                        "aineisto_nimi": indeksi_nimi,
                        "ehdot": nykyiset_ehdot,
                        "osumia": resp.get("hits", {}).get("total", {}).get("value", 0),
                        "tulokset": resp.get("hits", {}).get("hits", []),
                        "resp": resp,
                        "indeksi_avain": indeksi_avain,
                        "kysely": kysely,
                    }

        haku = st.session_state.get("hakutulos")
        if haku and haku.get("ehdot") != nykyiset_ehdot:
            # Käyttäjä on muuttanut hakua tai rajauksia: kerrotaan, ettei alla oleva vielä vastaa niitä
            with st.container(key="muutosilmoitus", horizontal=True, vertical_alignment="center"):
                st.markdown("**Muutit hakuehtoja.** Alla näkyvät vielä edellisen haun tulokset. "
                            "Päivitä haku, niin tulokset vastaavat uusia ehtoja.")
                st.button("Päivitä haku", type="primary", on_click=_aseta_ja_hae,
                          icon=":material/refresh:", key="paivita_haku")
        if haku and haku["osumia"] > 0:
            nayta_tulokset(haku)
        elif haku:
            nayta_nollatulos(haku)
        elif not aja:
            st.markdown(
              "<p class='johdanto'>Käräjien pöytäkirjoissa mainitaan talollisia, torppareita, "
              "leskiä ja lapsia: maakauppoja, perinnönjakoja, velkoja ja riitoja. Kirjoita hakuun "
              "sukunimi tai talon nimi, niin näet asiakirjat, joissa se esiintyy, ja pääset "
              "alkuperäiseen käsinkirjoitettuun sivuun.</p>",
              unsafe_allow_html=True)
            st.markdown("**Kokeile esimerkkihakua:**")
            sarakkeet = st.columns(len(ESIMERKKIHAUT) + 2)
            for sarake, esim in zip(sarakkeet, ESIMERKKIHAUT):
                sarake.button(esim, on_click=_aseta_ja_hae, kwargs={"hakusana": esim},
                              width="stretch")

    with tab_suosikit:
        nayta_suosikit()

    with tab_ohje:
        st.subheader("Näin haet")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Yksi sana**")
            st.code("Mäntylä", language=None)
            st.caption("Hakee kaikki maininnat sanasta.")

            st.markdown("**Usea sana**")
            st.code("Juho Mäntylä Jurva", language=None)
            st.caption("Kaikkien sanojen pitää löytyä samasta asiakirjasta. Asiakirjat, joissa sanat ovat "
                       "lähekkäin, nousevat kärkeen. Jos valitset ”Riittää, että yksi sanoista löytyy”, yksikin sana riittää.")

            st.markdown("**Tarkka fraasi**")
            st.code('"Koivumäen talo"', language=None)
            st.caption("Sanojen pitää esiintyä peräkkäin tässä järjestyksessä.")

        with col2:
            st.markdown("**Jompikumpi**")
            st.code("Mäntylä OR Männylä", language=None)
            st.caption("Kumpi tahansa riittää. Hyödyllinen vanhoille kirjoitusasuille.")

            st.markdown("**Sanan alku**")
            st.code("Mänty*", language=None)
            st.caption("Löytää kaikki Mänty-alkuiset sanat: Mäntylä, Mäntymäki jne.")

            st.markdown("**Etunimen vanhat muodot**")
            st.code("Juho", language=None)
            st.caption("Hakee myös Johan, Johannes, Juhana, Juhani. Valinta on oletuksena päällä "
                       "ja löytyy sivupalkin kohdasta Nimet ja kirjoitusasu.")

        st.divider()
        st.subheader("Aineistot")
        a_vasen, a_oikea = st.columns([3, 2], gap="large")
        with a_oikea:
            st.image("static/kuvat/ritaalankoski-1912.jpg",
                     caption="Kyrönjoen Ritaalankoski, Isokyrö, 1912.")
        with a_vasen:
          st.markdown("""
| Aineisto | Sisältö | Aikaväli | Kieli |
|---|---|---|---|
| Tuomiokirjat | Yli 7 miljoonaa sivua käräjien pöytäkirjoja | 1600–1900-luvut | ruotsi, suomi |
| Voudintilit | Ruotsin vallan aikainen verotusaineisto | 1537–1634 | ruotsi |
| Diplomatarium Fennicum | Keskiaikaiset asiakirjat | n. 1100–1540 | latina, ruotsi |
""")
          st.info("Tuomiokirjat ovat 1600–1800-luvuilla pääosin ruotsiksi. Hae myös ruotsinkielisillä "
                  "muodoilla: Ilmajoki → Ilmola, Vaasa → Wasa tai Vasa, Juho → Johan.",
                  icon=":material/translate:")

        st.divider()
        st.subheader("Aihetunnisteet")
        st.markdown("""
Tuloksiin lisätään tekstin perusteella aihetunnisteita, jotka kertovat nopeasti, mistä asiakirjassa on kyse:
**Oikeudenkäynti, Kauppa ja velka, Perintö ja omaisuus, Maatalous, Väkivalta, Kirkko ja uskonto.**

Tunnisteiden, maakunnan ja vuosisadan mukaan voi rajata tuloksia kohdasta *Järjestä ja rajaa tuloksia*.
Tunnisteet ovat suuntaa antavia, koska ne perustuvat yksittäisiin sanoihin.
""")

        st.divider()
        st.subheader("Vinkkejä sukututkimukseen")
        v_vasen, v_oikea = st.columns([3, 1.4], gap="large")
        with v_oikea:
            st.image("static/kuvat/poika-haravoi-hartola.jpg", caption="Kesä Hartolassa.")
        with v_vasen:
          st.markdown("""
- **Kokeile ruotsinkielisiä muotoja.** *Juho Mäntylä* esiintyy usein muodossa *Johan Mäntylä* tai *Johan Månttylä*.
- **Käytä sanan alkua epävarmoissa nimissä.** `Mänty*` löytää kaikki muunnokset.
- **Rajaa aikaväli.** Jos tiedät henkilön eläneen n. 1780–1830, rajaa haku siihen.
- **Valitse tuomiokunta**, jos tiedät pitäjän. Valitse ensin maakunta sivupalkista.
- **Tallenna löydöt suosikeiksi.** Tuloksen *Tallenna suosikiksi* -painike vie asiakirjan Suosikit-välilehdelle, jossa voit lisätä oman muistiinpanon.
- **Avaa alkuperäinen asiakirja.** Linkki vie Astiaan, jossa näet käsinkirjoitetun sivun. Koneellisesti tunnistettu teksti sisältää virheitä.
""")

        st.divider()
        st.subheader("Kuvat")
        st.markdown("\n".join(f"- [{nimi}]({url}). {lahde}" for nimi, lahde, url in KUVALAHTEET))

        st.divider()
        st.subheader("API-avain")
        st.markdown("Haku käyttää Kansallisarkiston hakurajapintaa, johon tarvitaan avain. "
                    "Avainta voi pyytää Kansallisarkiston asiakaspalvelusta ([kansallisarkisto.fi](https://kansallisarkisto.fi)).")


if __name__ == "__main__":
    main()
