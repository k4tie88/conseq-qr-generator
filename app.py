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
    
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()

    # --- NOVÁ STRATEGIE: POŘADÍ ÚČTŮ ---
    # Najdeme všechny formáty účtů v celém PDF
    all_found = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', full_text)
    
    # Vyčištění a formátování nalezených účtů
    valid_accounts = [f"{m[0].strip()} / {m[1].strip()}" for m in all_found]

    # Logika pro Conseq:
    # 1. účet v PDF bývá klientka (sekce A) -> ignorujeme nebo dáme až na konec
    # 2. účet v PDF bývá CZK v tabulce (sekce Instrukce)
    # 3. účet v PDF bývá EUR v tabulce (sekce Instrukce)
    
    acc_czk = None
    acc_eur = None
    
    if len(valid_accounts) >= 3:
        acc_czk = valid_accounts[1] # Druhý nalezený v pořadí
        acc_eur = valid_accounts[2] # Třetí nalezený v pořadí
    elif len(valid_accounts) == 2:
        acc_czk = valid_accounts[1]

    # --- UI ---
    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚙️ Parametry platby")
        
        # Volba režimu (DIP vs Klasik)
        if is_dip:
            st.success("✅ Smlouva DIP")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Bulk)"])
        else:
            st.warning("📄 Klasická smlouva (bez DIP)")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        # Volba měny
        currency = st.selectbox("Měna platby:", ["CZK", "EUR"])
        
        # Přiřazení na základě tabulky
        detected_acc = acc_czk if currency == "CZK" else acc_eur
        
        if detected_acc:
            st.info(f"📍 Účet pro {currency} z tabulky: **{detected_acc}**")
        else:
            st.error(f"❌ Účet pro {currency} nenalezen.")
            detected_acc = st.text_input("Zadejte účet ručně:")

        amt = st.number_input(f"Částka ({currency}):", value=0.0)
        
        # Detekce VS
        vs_match = re.search(r'41\d{8}', full_text)
        f_vs = st.text_input("Variabilní symbol (Smlouva):", value=vs_match.group(0) if vs_match else "")
        
        # Logika SS
        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            f_ss = st.text_input("Zadejte IČO (pro SS):")

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