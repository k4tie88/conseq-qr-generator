import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- MATEMATICKÝ PŘEVOD NA IBAN ---
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

st.set_page_config(page_title="Conseq Fix", layout="wide")
st.title("🏦 Conseq QR (Varianta 1 - Stabilní)")

file = st.file_uploader("NAHRAJTE PDF", type="pdf")

if file:
    with pdfplumber.open(file) as pdf:
        # Přečteme VŠECHNO a smažeme zbytečné mezery kolem slov, ale necháme ty v číslech
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
    col1, col2 = st.columns(2)
    with col1:
        curr = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        
        # --- AGRESIVNÍ HLEDÁNÍ VS ---
        # Hledáme 10 čísel, která začínají na 41 (typické pro Conseq smlouvy)
        vs_matches = re.findall(r'41\d{8}', full_text)
        found_vs = vs_matches[0] if vs_matches else ""

        # --- AGRESIVNÍ HLEDÁNÍ ÚČTU ---
        found_acc = ""
        # Najdeme místo, kde je měna a vezmeme text za ní
        search_pattern = rf'{curr}[:\s]*([\d\s/]+)'
        acc_match = re.search(search_pattern, full_text)
        if acc_match:
            raw_acc = acc_match.group(1).strip()
            # Vezmeme jen to, co vypadá jako účet (čísla a lomítko)
            clean_acc_match = re.search(r'(\d[\d\s]*/\s*\d{4})', raw_acc)
            if clean_acc_match:
                found_acc = re.sub(r'\s+', '', clean_acc_match.group(1))

        u_acc = st.text_input("Účet (nalezen):", value=found_acc)
        u_vs = st.text_input("Variabilní symbol:", value=found_vs)
        u_ss = st.text_input("Specifický symbol:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

    with col2:
        st.subheader("QR Platba")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                pay = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                st.image(segno.make(pay).to_pil(scale=10))
                st.success(f"IBAN: {iban}")
                st.code(pay)
            else: st.error("Nelze vytvořit IBAN")
        else: st.warning("Čekám na data z PDF...")
