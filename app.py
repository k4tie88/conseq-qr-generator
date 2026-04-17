import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (Čisté řešení bez mezer a pomlček) ---
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

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    all_accounts = []
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"
            # Najdeme všechna čísla účtů na dané stránce
            found = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', text)
            for f in found:
                # Vyčistíme číslo od mezer a pomlček hned při nálezu
                clean_num = re.sub(r'\D', '', f[0])
                all_accounts.append(f"{clean_num} / {f[1]}")

    # Základní detekce DIP a VS
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ" in full_text.upper()
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚙️ Parametry platby")
        if is_dip:
            st.success("✅ Smlouva DIP")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Hromadná)"])
        else:
            st.warning("📄 Klasická smlouva")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        currency = st.selectbox("Měna platby:", ["CZK", "EUR"])

        # --- LOGIKA POŘADÍ ÚČTŮ ---
        detected_acc = None
        try:
            if rezim == "Zaměstnanec":
                # Index 1 = CZK, Index 2 = EUR (Index 0 je klient)
                detected_acc = all_accounts[1] if currency == "CZK" else all_accounts[2]
            elif rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
                # Index 3 = Obvykle první účet v tabulce zaměstnavatele
                detected_acc = all_accounts[3]
            elif rezim == "Zaměstnavatel - Var 2 (Hromadná)":
                # Index 4 = Druhý účet v tabulce zaměstnavatele
                detected_acc = all_accounts[4]
        except IndexError:
            # Fallback pokud jich najde méně
            detected_acc = all_accounts[1] if len(all_accounts) > 1 else None

        if detected_acc:
            st.info(f"📍 Detekován účet: **{detected_acc}**")
        else:
            st.error("❌ Účet v PDF nenalezen.")
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
            
            if st.button("VYGENEROVAT"):
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(amt)}*CC:{currency}*X-VS:{f_vs}"
                if f_ss: payload += f"*X-SS:{f_ss}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=12, border=4)
                st.image(out)
                st.success(f"BÚ: {detected_acc} | VS: {f_vs} | SS: {f_ss}")