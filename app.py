import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK ---
def czech_to_iban(account_number, bank_code):
    clean_acc = account_number.replace(" ", "").replace("-", "")
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
st.title("🏦 Conseq QR Generátor")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    
    # Detekce typu smlouvy a VS
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    # SEKCIONOVÁNÍ TEXTU (Klíč k úspěchu)
    # Hledáme začátek instrukcí pro zaměstnavatele
    emp_header = "Instrukce pro platby příspěvků zaměstnavatele"
    emp_idx = full_text.find(emp_header)
    
    if emp_idx != -1:
        client_part = full_text[:emp_idx]
        employer_part = full_text[emp_idx:]
    else:
        client_part = full_text
        employer_part = ""

    # Funkce pro extrakci účtů z konkrétní části textu
    def extract_accs(text_block):
        matches = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', text_block)
        return [f"{m[0].strip()} / {m[1].strip()}" for m in matches]

    c_accs = extract_accs(client_part)
    e_accs = extract_accs(employer_part)

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚙️ Parametry platby")
        if is_dip:
            st.success("✅ Smlouva DIP")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Hromadná)"])
        else:
            st.warning("📄 Klasická smlouva (bez DIP)")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        currency = st.selectbox("Měna:", ["CZK", "EUR"])

        # PŘIŘAZENÍ ÚČTU DLE LOGIKY TABULEK
        detected_acc = None
        if rezim == "Zaměstnanec":
            # 1. účet v client_part je obvykle bankovní spojení klienta (A), 2. je CZK, 3. je EUR
            if len(c_accs) >= 3:
                detected_acc = c_accs[1] if currency == "CZK" else c_accs[2]
            elif len(c_accs) == 2:
                detected_acc = c_accs[1]
        elif rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            # První účet v sekci zaměstnavatele
            detected_acc = e_accs[0] if len(e_accs) > 0 else None
        elif rezim == "Zaměstnavatel - Var 2 (Hromadná)":
            # Druhý účet v sekci zaměstnavatele
            detected_acc = e_accs[1] if len(e_accs) > 1 else None

        if detected_acc:
            st.info(f"📍 Detekován účet: **{detected_acc}**")
        else:
            st.error("❌ Účet v PDF nebyl nalezen v příslušné sekci.")
            detected_acc = st.text_input("Zadejte účet ručně:")

        amt = st.number_input(f"Částka ({currency}):", value=0.0, step=100.0)
        f_vs = st.text_input("Variabilní symbol:", value=found_vs)
        
        # Specifický symbol
        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            f_ss = st.text_input("IČO pro SS (povinné pro Var 1):")

    with col2:
        st.subheader("📱 QR kód")
        if detected_acc and "/" in detected_acc:
            acc_p, bank_p = detected_acc.split("/")
            iban = czech_to_iban(acc_p.strip(), bank_p.strip())
            
            if st.button("VYGENEROVAT QR"):
                if "Var 1" in rezim and not f_ss:
                    st.error("Zadejte IČO pro Specifický symbol!")
                else:
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(amt)}*CC:{currency}*X-VS:{f_vs}"
                    if f_ss: payload += f"*X-SS:{f_ss}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=12, border=4)
                    st.image(out)
                    st.write(f"🏦 BÚ: {detected_acc} | VS: {f_vs} | SS: {f_ss}")