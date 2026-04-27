import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

def vytvor_iban_dynamicky(account_str):
    try:
        clean = re.sub(r'[^\d/]', '', account_str)
        if "/" not in clean: return None
        num, bank = clean.split("/")
        prefix, number = (num[:-10], num[-10:]) if len(num) > 10 else ("0", num)
        prefix, number, bank = prefix.zfill(6), number.zfill(10), bank.zfill(4)
        check_str = f"{bank}{prefix}{number}123500"
        rem = int(check_str) % 97
        return f"CZ{str(98 - rem).zfill(2)}{bank}{prefix}{number}"
    except: return None

st.set_page_config(page_title="Conseq QR Generátor", layout="wide")
st.title("🏦 Conseq QR Generátor (Standard & DIP)")

file = st.file_uploader("1. NAHRAJTE PDF SMLOUVU", type="pdf")

if file:
    with pdfplumber.open(file) as pdf:
        # Vytáhneme text ze všech stran
        pages = [p.extract_text() for p in pdf.pages]
        raw_txt = "\n".join(pages)
        
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Parametry platby")
        typ = st.radio("Typ platby:", ["Zaměstnanec (Varianta 1)", "Zaměstnavatel (DIP - Var. 2)"])
        curr = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        
        # --- SPOLEČNÉ: VS (Číslo smlouvy) ---
        found_vs = ""
        vs_m = re.search(r'Číslo\s+smlouvy\s*[:\s]*([\d\s]+)', raw_txt, re.IGNORECASE)
        if vs_m: found_vs = re.sub(r'\s+', '', vs_m.group(1))[:10]

        # --- VARIANTA 1: ZAMĚSTNANEC ---
        if "Zaměstnanec" in typ:
            found_ss = "999"
            found_ks = ""
            found_acc = ""
            acc_p = rf'Číslo\s+účtu\s+v\s+{curr}\s*[:\s]*([\d\s\/-]+)'
            acc_m = re.search(acc_p, raw_txt, re.IGNORECASE)
            if acc_m: found_acc = re.sub(r'[\s-]', '', acc_m.group(1))

        # --- VARIANTA 2: ZAMĚSTNAVATEL (DIP) ---
        else:
            subtyp = st.selectbox("Podtyp DIP platby:", ["A) Příspěvek zaměstnavatele", "B) Platba klienta (hrazená zam.)"])
            found_ks, found_acc, found_ss = "", "", ""
            
            # Hledáme tabulku DIP (sekce zaměstnavatele)
            dip_section = ""
            for p in pages:
                if "ZAMĚSTNAVATELEM" in p.upper():
                    dip_section = p
                    break
            
            if dip_section:
                lines = [l for l in dip_section.split('\n') if '/' in l and '2700' in l]
                if "A)" in subtyp and len(lines) >= 1:
                    found_acc = re.sub(r'[\s-]', '', re.search(r'(\d[\d\s\/-]+\/\d{4})', lines[0]).group(1))
                    found_ks = re.findall(r'\d{4}', lines[0])[-1]
                    ico = st.text_input("Zadejte IČO zaměstnavatele:")
                    found_ss = re.sub(r'\D', '', ico)
                elif "B)" in subtyp and len(lines) >= 2:
                    found_acc = re.sub(r'[\s-]', '', re.search(r'(\d[\d\s\/-]+\/\d{4})', lines[1]).group(1))
                    found_ks = re.findall(r'\d{4}', lines[1])[-1]
                    found_ss = "" # Dle tabulky nevyplňovat

        # --- FORMULÁŘ ---
        u_acc = st.text_input("Účet (vysáto):", value=found_acc)
        u_vs = st.text_input("VS (Smlouva):", value=found_vs)
        u_ss = st.text_input("SS:", value=found_ss)
        u_ks = st.text_input("KS:", value=found_ks)
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=500.0)

    with col2:
        st.subheader("Výsledek")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                parts = [f"SPD*1.0*ACC:{iban}", f"AM:{u_amt:.2f}", f"CC:{curr}", f"X-VS:{u_vs}"]
                if u_ss: parts.append(f"X-SS:{u_ss}")
                if u_ks: parts.append(f"X-KS:{u_ks}")
                pay = "*".join(parts) + "*"
                st.image(segno.make(pay).to_pil(scale=10), caption="Skenujte v bance")
                st.success(f"IBAN: {iban}")
