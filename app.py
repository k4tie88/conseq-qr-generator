import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK ---
def czech_to_iban(account_number, bank_code):
    clean_acc = account_number.replace(" ", "").replace("-", "")
    if len(clean_acc) > 10:
        prefix = clean_acc[:-10]
        acc = clean_acc[-10:]
    else:
        if len(clean_acc) > 6: # Typicky Conseq 6850 057 -> 6850 + 057
            prefix = clean_acc[:4]
            acc = clean_acc[4:]
        else:
            prefix = "0"
            acc = clean_acc
    prefix_str = prefix.zfill(6)
    acc_str = acc.zfill(10)
    check_str = f"{bank_code}{prefix_str}{acc_str}123500"
    mod = int(check_str) % 97
    check_digits = 98 - mod
    return f"CZ{check_digits:02d}{bank_code}{prefix_str}{acc_str}"

st.set_page_config(page_title="Conseq QR Generátor PRO", layout="wide")
st.title("🏦 Conseq QR Generátor")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()
    
    # --- LOGIKA VYHLEDÁVÁNÍ ÚČTŮ ---
    def get_conseq_account(currency, text):
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if f"Číslo účtu v {currency}" in line:
                # Koukáme na tento řádek a jeden další pod ním
                search_area = line + " " + (lines[i+1] if i+1 < len(lines) else "")
                match = re.search(r'([\d\s]{2,16})\s*/\s*(\d{4})', search_area)
                if match:
                    return f"{match.group(1).strip()} / {match.group(2).strip()}"
        return None

    acc_czk = get_conseq_account("CZK", full_text)
    acc_eur = get_conseq_account("EUR", full_text)
    
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚙️ Parametry platby")
        
        if is_dip:
            st.success("✅ Detekována smlouva DIP")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Hromadná)"])
        else:
            st.warning("📄 Klasická smlouva (bez DIP)")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        currency = st.selectbox("Měna platby:", ["CZK", "EUR"])
        detected_acc = acc_czk if currency == "CZK" else acc_eur
        
        if detected_acc:
            st.info(f"📍 Nalezen účet: **{detected_acc}**")
        else:
            st.error(f"❌ Účet pro {currency} v PDF nenalezen!")
            # Debug: ukážeme kousek textu, kde by to mělo být
            st.write("Zkuste zadat účet ručně:")
            detected_acc = st.text_input("BÚ (např. 6850 057 / 2700):")

        amt = st.number_input(f"Částka ({currency}):", value=0.0)
        f_vs = st.text_input("Variabilní symbol (Smlouva):", value=found_vs)
        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            f_ss = st.text_input("Zadejte IČO pro SS:")

    with col2:
        st.subheader("📱 QR kód")
        if detected_acc and "/" in detected_acc:
            acc_p, bank_p = detected_acc.split("/")
            iban = czech_to_iban(acc_p.strip(), bank_p.strip())

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
                    st.write(f"🏦 BÚ: {detected_acc} | VS: {f_vs} | SS: {f_ss}")
                    st.caption(f"IBAN: {iban}")