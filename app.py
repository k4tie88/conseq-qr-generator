import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. UNIVERZÁLNÍ PŘEVODNÍK NA IBAN ---
def czech_to_iban(account_number, bank_code):
    if '-' in account_number:
        prefix, acc = account_number.split('-')
    else:
        prefix, acc = "0", account_number
    prefix, acc = prefix.zfill(6), acc.zfill(10)
    check_str = f"{bank_code}{prefix}{acc}123500"
    mod = int(check_str) % 97
    check_digits = 98 - mod
    return f"CZ{check_digits:02d}{bank_code}{prefix}{acc}"

st.set_page_config(page_title="Conseq QR Generátor PRO", layout="wide")

st.title("🏦 Conseq QR Generátor (Klasik i DIP)")
st.markdown("Nahrajte smlouvu a vyberte typ platby. Všechny účty jsou automaticky převáděny na IBAN.")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    
    # Detekce účtů v PDF
    acc_pattern = r'(?:(\d{0,6})-)?(\d{2,10})\s*/\s*(\d{4})'
    found_accounts = re.findall(acc_pattern, full_text)
    unique_accounts = [f"{p+'-' if p else ''}{a} / {b}" for p, a, b in found_accounts]
    unique_accounts = list(dict.fromkeys(unique_accounts)) # Odstranění duplicit

    # Detekce čísla smlouvy (VS) - začíná 41...
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📋 Nastavení platby")
        
        # Volba role
        rezim = st.radio("Kdo provádí platbu?", 
                         ["Klient (zaměstnanec)", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Bulk)"])
        
        # Výběr účtu z PDF
        selected_acc = st.selectbox("Cílový účet nalezený v PDF:", unique_accounts if unique_accounts else ["Nenalezeno"])
        
        # Měna a částka
        c1, c2 = st.columns(2)
        with c1:
            currency = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        with c2:
            amount = st.number_input(f"Částka ({currency}):", value=0.0, step=100.0)

        # Variabilní symbol (vždy číslo smlouvy)
        final_vs = st.text_input("Variabilní symbol (Číslo smlouvy):", value=found_vs)

        # LOGIKA SPECIFICKÉHO SYMBOLU
        final_ss = ""
        if rezim == "Klient (zaměstnanec)":
            final_ss = "999"
            st.info("Specifický symbol nastaven na 999 (pravidelná investice).")
        
        elif rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            ico = st.text_input("Zadejte IČO zaměstnavatele (pro Specifický symbol):")
            final_ss = ico
            st.warning("U této varianty je IČO povinné pro správné párování.")
            
        elif rezim == "Zaměstnavatel - Var 2 (Bulk)":
            final_ss = ""
            st.info("U hromadné platby (Var 2) zůstává Specifický symbol prázdný.")

    with col2:
        st.subheader("📱 QR kód pro banku")
        if selected_acc != "Nenalezeno" and selected_acc != "Nenalezeno":
            acc_part, bank_part = selected_acc.split(" / ")
            target_iban = czech_to_iban(acc_part, bank_part)

            if st.button("GENEROVAT QR KÓD"):
                if rezim == "Zaměstnavatel - Var 1 (Příspěvek)" and not final_ss:
                    st.error("Pro Variantu 1 musí být vyplněno IČO!")
                else:
                    amt_fmt = "{:.2f}".format(amount)
                    # Sestavení SPD řetězce (Specifický symbol je X-SS)
                    payload = f"SPD*1.0*ACC:{target_iban}*AM:{amt_fmt}*CC:{currency}*X-VS:{final_vs}"
                    if final_ss:
                        payload += f"*X-SS:{final_ss}"
                    payload += "*" # Ukončovací hvězdička
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=12, border=4)
                    
                    st.image(out)
                    
                    # Finální shrnutí
                    st.success("Platba připravena k naskenování")
                    st.write(f"**Režim:** {rezim}")
                    st.write(f"**IBAN:** `{target_iban}`")
                    st.write(f"**VS:** {final_vs} | **SS:** {final_ss if final_ss else '(prázdný)'}")