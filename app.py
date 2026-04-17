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
st.title("🏦 Conseq QR Generátor")

EMP_ACC_FIXED = "1388083926 / 2700"

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

found_vs = ""
c_accs = []

if file:
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"
            found = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', text)
            for f in found:
                clean_num = re.sub(r'\D', '', f[0])
                c_accs.append(f"{clean_num} / {f[1]}")
        
        vs_match = re.search(r'41\d{8}', full_text)
        found_vs = vs_match.group(0) if vs_match else ""

st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("⚙️ Parametry platby")
    
    rezim = st.radio("Kdo platí?", [
        "Zaměstnanec", 
        "Zaměstnavatel - Varianta 1 (Příspěvek na DIP)", 
        "Zaměstnavatel - Varianta 2 (Hromadná platba)"
    ])
    
    currency = st.selectbox("Měna platby:", ["CZK", "EUR"])

    detected_acc = None
    ks = ""  # Default je prázdný KS
    f_ss = ""

    if rezim == "Zaměstnanec":
        f_ss = "999"
        ks = "" # U zaměstnance žádný KS není
        if len(c_accs) >= 3:
            detected_acc = c_accs[1] if currency == "CZK" else c_accs[2]
        else:
            detected_acc = "6850057 / 2700" if currency == "CZK" else "6850081 / 2700"

    elif rezim == "Zaměstnavatel - Varianta 1 (Příspěvek na DIP)":
        detected_acc = EMP_ACC_FIXED
        ks = "3552" # POUZE TADY JE KS 3552
        f_ss = st.text_input("IČO zaměstnavatele (SS):")

    elif rezim == "Zaměstnavatel - Varianta 2 (Hromadná platba)":
        detected_acc = EMP_ACC_FIXED
        ks = "" # Tady KS taky není
        f_ss = st.text_input("Období RRRRMM (SS):")

    st.info(f"🏦 Cílový účet: **{detected_acc}**")
    amt = st.number_input(f"Částka ({currency}):", value=0.0)
    f_vs = st.text_input("Variabilní symbol:", value=found_vs)

with col2:
    st.subheader("📱 QR kód")
    if detected_acc:
        acc_p, bank_p = detected_acc.split(" / ")
        iban = czech_to_iban(acc_p.strip(), bank_p.strip())
        
        if st.button("VYGENEROVAT QR KÓD"):
            if "Zaměstnavatel" in rezim and not f_ss:
                st.error("Doplňte Specifický symbol!")
            else:
                # Sestavení řetězce - KS se přidá jen když není prázdný
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(amt)}*CC:{currency}*X-VS:{f_vs}*X-SS:{f_ss}"
                if ks:
                    payload += f"*X-KS:{ks}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=12, border=4)
                st.image(out)
                st.success(f"BÚ: {detected_acc} | VS: {f_vs} | SS: {f_ss} | KS: {ks if ks else 'není'}")