import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK ---
def czech_to_iban(account_number, bank_code):
    clean_acc = re.sub(r'\D', '', account_number)
    if len(clean_acc) > 10:
        prefix, acc = clean_acc[:-10], clean_acc[-10:]
    elif len(clean_acc) > 6:
        prefix, acc = clean_acc[:4], clean_acc[4:]
    else:
        prefix, acc = "0", clean_acc
    p_str, a_str = prefix.zfill(6), acc.zfill(10)
    check_str = f"{bank_code}{p_str}{a_str}123500"
    mod = int(check_str) % 97
    check_digits = 98 - mod
    return f"CZ{check_digits:02d}{bank_code}{p_str}{a_str}"

st.set_page_config(page_title="Conseq QR Generátor PRO", layout="wide")
st.title("🏦 Conseq QR Generátor (Fixní účty)")

# Definice účtů natvrdo podle tvých podkladů
ACCOUNTS = {
    "Zaměstnanec": {
        "CZK": "6850057 / 2700",
        "EUR": "6850081 / 2700"
    },
    "Zaměstnavatel - Var 1 (Příspěvek)": {
        "CZK": "6850065 / 2700"
    },
    "Zaměstnavatel - Var 2 (Hromadná)": {
        "CZK": "6850014 / 2700"
    }
}

file = st.file_uploader("Nahrajte PDF pro vytažení VS", type="pdf")

found_vs = ""
is_dip = False

if file:
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        # Hledáme jen Variabilní symbol (číslo smlouvy 41...)
        vs_match = re.search(r'41\d{8}', full_text)
        found_vs = vs_match.group(0) if vs_match else ""
        is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ" in full_text.upper()

st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("⚙️ Parametry platby")
    
    # Režim platby
    options = ["Zaměstnanec"]
    if is_dip or not file: # Pokud není PDF, necháme možnosti otevřené
        options += ["Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Hromadná)"]
    
    rezim = st.radio("Kdo platí?", options)
    
    # Výběr měny (pro zaměstnavatele obvykle jen CZK, ale necháme volbu)
    currency = st.selectbox("Měna:", ["CZK", "EUR"])
    
    # Výběr účtu z naší "pevné" tabulky
    if rezim in ACCOUNTS:
        detected_acc = ACCOUNTS[rezim].get(currency, ACCOUNTS[rezim].get("CZK"))
    else:
        detected_acc = "6850057 / 2700"

    st.info(f"🏦 Cílový účet (fixní): **{detected_acc}**")
    
    amt = st.number_input(f"Částka ({currency}):", value=0.0)
    f_vs = st.text_input("Variabilní symbol (ze smlouvy):", value=found_vs)
    
    f_ss = "999" if rezim == "Zaměstnanec" else ""
    if "Var 1" in rezim:
        f_ss = st.text_input("IČO pro Specifický symbol:")

with col2:
    st.subheader("📱 QR kód")
    if detected_acc:
        acc_p, bank_p = detected_acc.split(" / ")
        iban = czech_to_iban(acc_p, bank_p)
        
        if st.button("VYGENEROVAT"):
            if "Var 1" in rezim and not f_ss:
                st.error("Chybí IČO!")
            else:
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(amt)}*CC:{currency}*X-VS:{f_vs}"
                if f_ss: payload += f"*X-SS:{f_ss}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=12, border=4)
                st.image(out)
                st.success(f"Připraveno k platbě na účet {detected_acc}")