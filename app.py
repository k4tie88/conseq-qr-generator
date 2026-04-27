import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. MATEMATICKY PŘESNÝ PŘEVOD NA IBAN ---
def vytvor_iban_dynamicky(account_str):
    try:
        # 1. Totální očista: odstraníme mezery a vše co není číslo, lomítko nebo pomlčka
        clean_acc = re.sub(r'[^\d\/-]', '', account_str)
        
        if "/" not in clean_acc:
            return None
        
        # Rozdělení na číslo a kód banky
        full_number, bank_code = clean_acc.split("/")
        
        # Ošetření předčíslí (pokud je tam pomlčka)
        prefix = "0"
        number = full_number
        if "-" in full_number:
            prefix, number = full_number.split("-")
        
        # Doplnění nul na standardní délku (předčíslí 6, číslo 10, banka 4)
        prefix = prefix.zfill(6)
        number = number.zfill(10)
        bank_code = bank_code.zfill(4)
        
        # Výpočet kontrolních číslic (modulo 97)
        check_str = f"{bank_code}{prefix}{number}123500"
        remainder = int(check_str) % 97
        check_digits = str(98 - remainder).zfill(2)
        
        return f"CZ{check_digits}{bank_code}{prefix}{number}"
    except:
        return None

# --- 2. STREAMLIT APLIKACE ---
st.set_page_config(page_title="QR Generátor v6.8", layout="wide")
st.title("🏦 QR Generátor (IBAN fix)")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    if "pdf_raw" not in st.session_state or st.session_state.last_file != file.name:
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages:
                txt += page.extract_text() + "\n"
            st.session_state.pdf_raw = txt
            st.session_state.last_file = file.name

if "pdf_raw" in st.session_state:
    raw = st.session_state.pdf_raw
    col1, col2 = st.columns(2)
    
    with col1:
        curr = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        
        # --- HLEDÁNÍ VS ---
        vs_m = re.search(r'ČÍSLO\s+SMLOUVY:\s*(\d+)', raw, re.IGNORECASE)
        found_vs = vs_m.group(1) if vs_m else ""

        # --- HLEDÁNÍ ÚČTU (Ignoruje mezery) ---
        found_acc = ""
        # Najdeme text od "účtu v CZK" až po konec řádku
        pattern = rf'účtu\s+v\s+{curr}\s*:\s*([\d\s\/-]+)'
        acc_match = re.search(pattern, raw, re.IGNORECASE)
        
        if acc_match:
            # Tady to chytne i ty mezery (např. "6850 057 / 2700")
            raw_acc = acc_match.group(1).strip()
            # A tady ty mezery totálně odstraníme pro zobrazení
            found_acc = re.sub(r'\s+', '', raw_acc)

        u_acc = st.text_input("Číslo účtu (očištěno):", value=found_acc)
        u_vs = st.text_input("Variabilní symbol:", value=found_vs)
        u_ss = st.text_input("Specifický symbol:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

    with col2:
        st.subheader("Výsledek pro banku")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                # Sestavení QR řetězce (VŽDY S IBANEM)
                pay_str = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                
                qr = segno.make(pay_str, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                
                st.image(out, caption="Skenujte v bankovní aplikaci")
                st.success(f"Převedeno na IBAN: {iban}")
                st.code(pay_str)
            else:
                st.error("❌ Nepodařilo se vytvořit platný IBAN. Zkontrolujte formát účtu.")
        else:
            st.info("Doplňte údaje pro vygenerování QR kódu.")
