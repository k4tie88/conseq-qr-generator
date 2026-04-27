import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- IBAN PŘEVODNÍK ---
def vytvor_iban_dynamicky(account_str):
    try:
        clean = re.sub(r'[^\d/]', '', account_str)
        if "/" not in clean: return None
        num, bank = clean.split("/")
        prefix, number = (num[:-10], num[-10:]) if len(num) > 10 else ("0", num)
        prefix, number, bank = prefix.zfill(6), number.zfill(10), bank.zfill(4)
        check_str = f"{bank}{prefix}{number}123500"
        rem = int(check_str) % 97
        return f"CZ{str(98 - rem).zfill(2)}{bank}{prefix}{number}"
    except: return None

st.set_page_config(page_title="Conseq QR Precise", layout="wide")
st.title("🏦 Conseq QR - Cílené čtení z tabulky IZPP")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    with pdfplumber.open(file) as pdf:
        # 1. VEZMEME POUZE POSLEDNÍ STRANU
        last_page = pdf.pages[-1]
        last_page_text = last_page.extract_text()
        # 2. PRO CELÝ DOKUMENT (kvůli VS na začátku)
        full_text = "\n".join([p.extract_text() for p in pdf.pages])

    # --- LOGIKA VYHLEDÁVÁNÍ ---
    # VS hledáme kdekoli (bývá na začátku)
    vs_matches = re.findall(r'41\d{8}', full_text)
    found_vs = vs_matches[0] if vs_matches else ""

    st.sidebar.header("🔍 Kontrola poslední strany")
    if "Instrukce k zasílání" in last_page_text:
        st.sidebar.success("✅ Tabulka IZPP nalezena")
    else:
        st.sidebar.warning("⚠️ Nadpis IZPP na poslední straně nenalezen")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Parametry")
        curr = st.selectbox("Vyberte měnu (dle tabulky IZPP):", ["CZK", "EUR", "USD"])
        
        # --- PŘESNÉ HLEDÁNÍ V TABULCE ---
        found_acc = ""
        # Hledáme vzor: "Číslo účtu v [Měna]" a vezmeme první číslo s lomítkem za tím
        # Regex hledá název sloupce a pak "skáče" přes text až k číslu účtu
        pattern = rf'Číslo\s+účtu\s+v\s+{curr}.*?(\d[\d\s]*/\s*2700)'
        acc_match = re.search(pattern, last_page_text, re.DOTALL | re.IGNORECASE)
        
        if acc_match:
            # Vyčistíme mezery z nalezeného čísla (6850 057 / 2700 -> 6850057/2700)
            found_acc = re.sub(r'\s+', '', acc_match.group(1))

        u_acc = st.text_input("Číslo účtu (vytěženo z IZPP):", value=found_acc)
        u_vs = st.text_input("Variabilní symbol (Číslo smlouvy):", value=found_vs)
        u_ss = st.text_input("Specifický symbol:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=500.0)

    with col2:
        st.subheader("QR Platba")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                pay_str = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                st.image(segno.make(pay_str).to_pil(scale=10), caption=f"Cílový IBAN: {iban}")
                st.success("QR kód připraven k platbě")
            else:
                st.error("Chyba převodu na IBAN. Zkontrolujte číslo účtu.")
        else:
            st.warning("Data nebyla nalezena. Zkontrolujte, zda je PDF čitelné.")

    with st.expander("Zobrazit text poslední strany (pro kontrolu)"):
        st.text(last_page_text)
