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

    # Najdeme všechny účty ve formátu XXXXX / XXXX v celém PDF
    all_found = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', full_text)
    accounts = [f"{m[0].strip()} / {m[1].strip()}" for m in all_found]

    # Detekce VS
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
            st.warning("📄 Klasická smlouva (bez DIP)")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        currency = st.selectbox("Měna:", ["CZK", "EUR"])

        # --- LOGIKA VÝBĚRU ÚČTU PODLE REŽIMU A POŘADÍ V PDF ---
        # Indexy v poli 'accounts':
        # [0] = Klientka, [1] = CZK Zaměstnanec, [2] = EUR Zaměstnanec
        # [3] = CZK Zaměstnavatel (Var 1), [4] = CZK Zaměstnavatel (Var 2)
        
        detected_acc = None
        
        try:
            if rezim == "Zaměstnanec":
                detected_acc = accounts[1] if currency == "CZK" else accounts[2]
            elif rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
                # Bere první řádek z tabulky pro zaměstnavatele (obvykle 4. účet v PDF)
                detected_acc = accounts[3] if len(accounts) > 3 else accounts[1]
            elif rezim == "Zaměstnavatel - Var 2 (Hromadná)":
                # Bere druhý řádek z tabulky pro zaměstnavatele (obvykle 5. účet v PDF)
                detected_acc = accounts[4] if len(accounts) > 4 else accounts[1]
        except IndexError:
            detected_acc = accounts[1] if len(accounts) > 1 else None

        if detected_acc:
            st.info(f"📍 Účet pro {rezim} ({currency}): **{detected_acc}**")
        else:
            st.error("❌ Účet v PDF nenalezen.")
            detected_acc = st.text_input("Zadejte účet ručně:")

        amt = st.number_input(f"Částka ({currency}):", value=0.0)
        f_vs = st.text_input("Variabilní symbol:", value=found_vs)
        
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