import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (UPRAVENÝ PRO SPOJENÉ ČÍSLO) ---
def czech_to_iban(account_number, bank_code):
    # Odstraníme úplně všechno kromě číslic (mezery, pomlčky, tečky)
    clean_acc = re.sub(r'\D', '', account_number)
    
    # Rozdělení na předčíslí a hlavní číslo pro Conseq (4 + 7 nebo 4 + 6)
    if len(clean_acc) > 10:
        prefix, acc = clean_acc[:-10], clean_acc[-10:]
    elif len(clean_acc) > 6:
        # Standardní Conseq: prvních 4-6 čísel je prefix, zbytek účet
        # Např. 6850057 -> 6850 je prefix, 057 je účet
        prefix = clean_acc[:4]
        acc = clean_acc[4:]
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
    
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    # SEKCIONOVÁNÍ TEXTU DLE NADPISU
    emp_header = "Instrukce pro platby příspěvků zaměstnavatele"
    idx = full_text.find(emp_header)
    if idx != -1:
        client_part, employer_part = full_text[:idx], full_text[idx:]
    else:
        client_part, employer_part = full_text, ""

    def get_accounts(text_block):
        if not text_block: return []
        matches = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', text_block)
        # Tady číslo účtu hned vyčistíme od mezer a pomlček pro zobrazení
        return [f"{m[0].replace(' ', '').replace('-', '')} / {m[1].strip()}" for m in matches]

    c_accs = get_accounts(client_part)
    e_accs = get_accounts(employer_part)

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

        currency = st.selectbox("Měna platby:", ["CZK", "EUR"])

        detected_acc = None
        if rezim == "Zaměstnanec":
            if len(c_accs) >= 3:
                detected_acc = c_accs[1] if currency == "CZK" else c_accs[2]
            elif len(c_accs) >= 2:
                detected_acc = c_accs[1]
        elif "Zaměstnavatel" in rezim:
            if not e_accs:
                st.error("Sekce pro zaměstnavatele nebyla nalezena.")
            else:
                detected_acc = e_accs[0] if "Var 1" in rezim else (e_accs[1] if len(e_accs) > 1 else e_accs[0])

        if detected_acc:
            st.info(f"📍 Detekován účet: **{detected_acc}**")
        else:
            detected_acc = st.text_input("Zadejte účet ručně (např. 6850057 / 2700):")

        amt = st.number_input(f"Částka ({currency}):", value=0.0)
        f_vs = st.text_input("Variabilní symbol:", value=found_vs)
        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if "Var 1" in rezim:
            f_ss = st.text_input("IČO pro Specifický symbol:")

    with col2:
        st.subheader("📱 QR kód")
        if detected_acc and "/" in detected_acc:
            acc_p, bank_p = detected_acc.split("/")
            iban = czech_to_iban(acc_p.strip(), bank_p.strip())
            
            if st.button("VYGENEROVAT QR KÓD"):
                if "Var 1" in rezim and not f_ss:
                    st.error("Zadejte IČO!")
                else:
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(amt)}*CC:{currency}*X-VS:{f_vs}"
                    if f_ss: payload += f"*X-SS:{f_ss}"
                    payload += "*"
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=12, border=4)
                    st.image(out)
                    st.success(f"BÚ: {detected_acc} | VS: {f_vs} | SS: {f_ss if f_ss else 'není'}")