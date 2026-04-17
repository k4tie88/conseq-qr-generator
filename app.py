import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (OŠETŘENÝ PRO MEZERY) ---
def czech_to_iban(account_number, bank_code):
    # Odstraníme mezery z čísla účtu (např. "6850 057" -> "6850057")
    clean_acc = account_number.replace(" ", "")
    
    if '-' in clean_acc:
        prefix, acc = clean_acc.split('-')
    elif len(clean_acc) > 10: # Pokud je číslo dlouhé, zkusíme ho rozdělit (časté u Conseq)
        # Předpokládáme, že posledních 10 číslic je hlavní účet, zbytek prefix
        prefix = clean_acc[:-10]
        acc = clean_acc[-10:]
    else:
        prefix, acc = "0", clean_acc
        
    prefix, acc = prefix.zfill(6), acc.zfill(10)
    check_str = f"{bank_code}{prefix}{acc}123500"
    mod = int(check_str) % 97
    check_digits = 98 - mod
    return f"CZ{check_digits:02d}{bank_code}{prefix}{acc}"

st.set_page_config(page_title="Conseq QR Generátor PRO", layout="wide")
st.title("🏦 Conseq QR Generátor")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()
    
    # --- OPRAVENÉ VYHLEDÁVÁNÍ ÚČTŮ (BERE I MEZERY) ---
    def find_account_by_label(label, text):
        # Hledáme label a pak řetězec čísel a mezer zakončený lomítkem a kódem banky
        # Tento regex schroustne "6850 057 / 2700" i "6850057/2700"
        pattern = label + r'.*?([\d\s-]{2,15})\s*/\s*(\d{4})'
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            raw_acc = match.group(1).strip()
            bank_code = match.group(2).strip()
            return f"{raw_acc} / {bank_code}"
        return None

    acc_czk = find_account_by_label("Číslo účtu v CZK", full_text)
    acc_eur = find_account_by_label("Číslo účtu v EUR", full_text)
    
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
            st.warning("📄 Detekována klasická smlouva (bez DIP)")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])
        
        currency = st.selectbox("Měna platby:", ["CZK", "EUR"])
        detected_acc = acc_czk if currency == "CZK" else acc_eur
        
        if detected_acc:
            st.write(f"📍 Cílový účet z tabulky: **{detected_acc}**")
        else:
            st.error(f"❌ V tabulce nebyl nalezen účet pro {currency}!")
            detected_acc = st.text_input("Zadejte cílový účet ručně (např. 6850 057/2700):")

        amt = st.number_input(f"Částka ({currency}):", value=0.0, step=100.0)
        f_vs = st.text_input("Variabilní symbol (Číslo smlouvy):", value=found_vs)

        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            f_ss = st.text_input("Zadejte IČO zaměstnavatele (pro SS):")

    with col2:
        st.subheader("📱 QR kód a kontrola")
        if detected_acc and " / " in detected_acc:
            acc_p, bank_p = detected_acc.split(" / ")
            # Tady se volá opravený převodník
            iban = czech_to_iban(acc_p, bank_p)

            if st.button("VYGENEROVAT"):
                if "Var 1" in rezim and not f_ss:
                    st.error("Pro Variantu 1 musíte zadat IČO!")
                else:
                    amt_fmt = "{:.2f}".format(amt)
                    payload = f"SPD*1.0*ACC:{iban}*AM:{amt_fmt}*CC:{currency}*X-VS:{f_vs}"
                    if f_ss: payload += f"*X-SS:{f_ss}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=12, border=4)
                    st.image(out)
                    
                    st.success("Údaje pro kontrolu:")
                    st.write(f"🏦 **Bankovní účet:** {detected_acc}")
                    st.write(f"🌍 **IBAN:** `{iban}`")
                    st.write(f"💰 **Částka:** {amt_fmt} {currency}")
                    st.write(f"🔢 **VS:** {f_vs} | **SS:** {f_ss if f_ss else 'neuveden'}")