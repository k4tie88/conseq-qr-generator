import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

def cz_account_to_iban(account_str):
    # Odstranění všech mezer a speciálních mezer
    account_str = re.sub(r'\s+', '', account_str)
    if "/" not in account_str:
        return account_str
    
    full_number, bank_code = account_str.split("/")
    prefix = "000000"
    number = full_number
    
    if "-" in full_number:
        prefix, number = full_number.split("-")
        
    prefix = prefix.zfill(6)
    number = number.zfill(10)
    bank_code = bank_code.zfill(4)
    
    check_str = f"{bank_code}{prefix}{number}123500"
    remainder = int(check_str) % 97
    check_digits = str(98 - remainder).zfill(2)
    
    return f"CZ{check_digits}{bank_code}{prefix}{number}"

def extract_text_from_pdf(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                # Použijeme standardní extrakci, která lépe funguje s těmito sloupci
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.error(f"Chyba při čtení PDF: {e}")
    return text

st.set_page_config(page_title="DIP QR Generátor v33", layout="centered")

st.title("🎯 DIP QR Generátor")

if 'cached_text' not in st.session_state:
    st.session_state.cached_text = ""

uploaded_file = st.file_uploader("1. Nahraj PDF s instrukcemi", type="pdf")

if uploaded_file:
    st.session_state.cached_text = extract_text_from_pdf(uploaded_file)

if st.session_state.cached_text:
    text = st.session_state.cached_text
    
    # Detekce variant (Conseq dokumenty mají specifické texty)
    has_a = "Individuální platba příspěvku zaměstnavatele na DIP" in text
    has_b = "Individuální platba příspěvku Klienta na DIP hrazená zaměstnavatelem" in text

    col1, col2 = st.columns([1, 2])
    with col1:
        currency = st.selectbox("2. Měna", ["CZK", "USD", "EUR"])
    with col2:
        available_options = ["Standard (Klient - SS 999)"]
        if has_a: available_options.append("A) Zaměstnavatel (IČO v SS)")
        if has_b: available_options.append("B) Zaměstnavatel (Bez SS)")
        payment_type = st.selectbox("3. Typ platby", available_options)

    employer_ico = ""
    if "A)" in payment_type:
        employer_ico = st.text_input("4. IČO Zaměstnavatele", max_chars=8)

    # --- LOVCI DAT (Regexy upravené podle diagnostiky) ---
    
    # 1. Variabilní symbol (Číslo smlouvy)
    vs = ""
    vs_match = re.search(r'(?:ČÍSLO SMLOUVY|SMLOUVY)[:\s]*(\d+)', text, re.IGNORECASE)
    if vs_match:
        vs = vs_match.group(1)

    account = ""
    amount = "0.00"
    ss = ""
    ks = ""

    if "Standard" in payment_type:
        ss = "999"
        # 2. Účet (UniCredit formát: 6850 057 / 2700)
        # Hledáme "v [Měna]" a pak čísla s mezerami a lomítkem
        acc_pattern = rf'investice\s+v\s+{currency}.*?([\d\s]+/[\s]*\d+)'
        acc_match = re.
