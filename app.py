import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. MATEMATIKA IBAN ---
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

# --- 2. EXTRAKCE TABULEK A TEXTU ---
def extract_data_from_pdf(file):
    all_text = ""
    employer_table_data = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            p_text = page.extract_text() or ""
            all_text += p_text + "\n"
            if "INSTRUKCE K ZASÍLÁNÍ PENĚŽNÍCH PROSTŘEDKŮ ZAMĚSTNAVATELEM" in p_text:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and any("platba příspěvku" in str(cell) for cell in row):
                            employer_table_data.append([str(c).replace('\n', ' ').strip() for c in row])
    return all_text, employer_table_data

# --- 3. UI NASTAVENÍ ---
st.set_page_config(page_title="DIP QR Generátor v38", layout="centered")
st.title("🎯 DIP QR Generátor")

if 'cached_text' not in st.session_state:
    st.session_state.cached_text = ""
    st.session_state.employer_rows = []

uploaded_file = st.file_uploader("1. Nahraj PDF s instrukcemi", type="pdf")

if uploaded_file:
    with st.spinner('Analyzuji PDF...'):
        txt, rows = extract_data_from_pdf(uploaded_file)
        st.session_state.cached_text = txt
        st.session_state.employer_rows = rows

if st.session_state.cached_text:
    text = st.session_state.cached_text
    
    col1, col2 = st.columns([1, 2])
    with col1:
        currency = st.selectbox("2. Měna", ["CZK", "EUR", "USD"])
    with col2:
        payment_type = st.selectbox("3. Typ platby", [
            "Standard (Klient - SS 999)",
            "A) Individuální platba zaměstnavatelem",
            "B) Hromadná platba zaměstnavatelem (Klient)"
        ])

    vs = ""
    account = ""
    ks = ""
    ss = ""
    amount = "0.00"

    # VS z textu smlouvy
    vs_m = re.search(r'SMLOUVY[:\s]*(\d+)', text, re.IGNORECASE)
    if vs_m: vs = vs_m.group(1)

    if "Standard" in payment_type:
        ss = "999"
        all_accounts = re.findall(r'(\d[\d\s]*/\s*2700)', text)
        if len(all_accounts) >= 3:
            idx = {"CZK": 0, "EUR": 1, "USD": 2}.get(currency, 0)
            account = re.sub(r'\s+', '', all_accounts[idx])
    else:
        target_string = "Individuální platba příspěvku zaměstnavatele na DIP" if "A)" in payment_type else "Individuální platba příspěvku Klienta na DIP hrazená zaměstnavatelem"
        
        found_row = next((row for row in st.session_state.employer_rows if any(target_string in cell for cell in row)), None)
        
        if found_row:
            acc_candidates = [c for c in found_row if "/" in c]
            if acc_candidates: account = re.sub(r'\s+', '', acc_candidates[0])
            
            digits_in_row = [c for c in found_row if c.isdigit()]
            if digits_in_row: ks = digits_in_row[-1]
            
            if "A)" in payment_type:
                ico_input = st.text_input("4. Zadejte IČO zaměstnavatele (povinné pro SS)", max_chars=8)
                ss = re.sub(r'\D', '', ico_input)
            else:
                ss = "" # Varianta B: Nevyplňovat

    if account and vs:
        iban = cz_account_to_iban(account)
        # Sestavení SPAYD (pokud SS chybí u Var A, QR se vygeneruje bez něj, ale uživatel uvidí varování)
        spayd = f"SPD*1.0*ACC:{iban}*AM:{amount}*CC:{currency}*X-VS:{vs}"
        if ks: spayd += f"*X-KS:{ks}"
        if ss: spayd += f"*X-SS:{ss}"

        st.divider()
        qr = segno.make(spayd, error='M')
        out = BytesIO()
        qr.save(out, kind='png', scale=10, border=4)
        
        c_l, c_r = st.columns([1, 1])
        with c_l:
            st.image(out.getvalue(), caption="QR kód pro platbu")
        with c_r:
            st.subheader("Platební údaje:")
            st.write(f"**Účet:** `{account}`")
            st.write(f"**Variabilní symbol:** `{vs}`")
            if ks: st.write(f"**Konstantní symbol:** `{ks}`")
            
            # --- Speciální zobrazení pro SS ---
            if "A)" in payment_type:
                if not ss:
                    st.error("⚠️ SS: VYPLŇTE IČO!")
                else:
                    st.success(f"**Specifický symbol (IČO):** `{ss}`")
            else:
                st.write("**Specifický symbol:** (nevyplňovat)")
                
            st.info("Částka: 0.00 (vyplňte v bance)")
    else:
        st.warning("⚠️ Čekám na nahrání PDF nebo detekci údajů.")
