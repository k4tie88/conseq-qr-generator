import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

def cz_account_to_iban(account_str):
    account_str = re.sub(r'\s+', '', account_str)
    if "/" not in account_str: return account_str
    full_number, bank_code = account_str.split("/")
    prefix, number = ("000000", full_number)
    if "-" in full_number: prefix, number = full_number.split("-")
    check_str = f"{bank_code.zfill(4)}{prefix.zfill(6)}{number.zfill(10)}123500"
    remainder = int(check_str) % 97
    check_digits = str(98 - remainder).zfill(2)
    return f"CZ{check_digits}{bank_code.zfill(4)}{prefix.zfill(6)}{number.zfill(10)}"

def extract_text_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

st.set_page_config(page_title="DIP QR Generátor v36", layout="centered")
st.title("🎯 DIP QR Generátor")

if 'cached_text' not in st.session_state:
    st.session_state.cached_text = ""

uploaded_file = st.file_uploader("1. Nahraj PDF s instrukcemi", type="pdf")

if uploaded_file:
    st.session_state.cached_text = extract_text_from_pdf(uploaded_file)

if st.session_state.cached_text:
    text = st.session_state.cached_text
    
    col1, col2 = st.columns([1, 2])
    with col1:
        currency = st.selectbox("2. Měna", ["CZK", "EUR", "USD"])
    with col2:
        has_a = "Individuální platba příspěvku zaměstnavatele na DIP" in text
        options = ["Standard (Klient - SS 999)"]
        if has_a: options.append("A) Zaměstnavatel (IČO v SS)")
        payment_type = st.selectbox("3. Typ platby", options)

    # --- LOGIKA PŘIŘAZENÍ ÚČTŮ ---
    # Najdeme všechna čísla účtů ve formátu XXXXXX / 2700
    all_accounts = re.findall(r'(\d[\d\s]*/\s*2700)', text)
    
    account = ""
    if len(all_accounts) >= 3:
        if currency == "CZK": account = all_accounts[0]
        elif currency == "EUR": account = all_accounts[1]
        elif currency == "USD": account = all_accounts[2]
        # Vyčištění mezer z vybraného účtu
        account = re.sub(r'\s+', '', account)
    
    # VS - Číslo smlouvy
    vs = ""
    vs_m = re.search(r'SMLOUVY[:\s]*(\d+)', text, re.IGNORECASE)
    if vs_m: vs = vs_m.group(1)

    amount = "0.00"
    ss = "999" if "Standard" in payment_type else ""
    ks = ""
    
    if "A)" in payment_type:
        ico = st.text_input("4. IČO Zaměstnavatele", max_chars=8)
        ss = re.sub(r'\D', '', ico)
        ks_m = re.search(r'IČ\s+zaměstnavatele\s+(\d{4})', text, re.IGNORECASE)
        if ks_m: ks = ks_m.group(1)

    if account and vs:
        iban = cz_account_to_iban(account)
        spayd = f"SPD*1.0*ACC:{iban}*AM:{amount}*CC:{currency}*X-VS:{vs}"
        if ks: spayd += f"*X-KS:{ks}"
        if ss: spayd += f"*X-SS:{ss}"

        st.divider()
        qr = segno.make(spayd, error='M')
        out = BytesIO()
        qr.save(out, kind='png', scale=10, border=4)
        
        c_l, c_r = st.columns([1, 1])
        with c_l:
            st.image(out.getvalue(), caption="Naskenujte v bance")
        with c_r:
            st.subheader("Platební údaje:")
            st.write(f"**Banka:** UniCredit Bank")
            st.write(f"**Účet:** `{account}`")
            st.write(f"**IBAN:** `{iban}`")
            st.write(f"**VS:** `{vs}`")
            if ss: st.write(f"**SS:** `{ss}`")
            if ks: st.write(f"**KS:** `{ks}`")
            st.info("Částka je v QR kódu 0.00 (doplňte v bance).")
    else:
        st.warning("⚠️ Nepodařilo se detekovat účty. Zkuste jinou měnu nebo zkontrolujte PDF.")
