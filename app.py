import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- MATEMATICKÝ VÝPOČET IBAN ---
def cz_account_to_iban(account_str):
    account_str = account_str.replace(" ", "")
    if "/" not in account_str:
        return account_str
    
    full_number, bank_code = account_str.split("/")
    prefix = "000000"
    number = full_number
    
    if "-" in full_number:
        prefix, number = full_number.split("-")
        
    prefix = prefix.zfill(6)
    number = number.zfill(10)
    bank_code = bank_code.zfill(4)
    
    # Sestavení řetězce pro modulo (Banka + Prefix + Číslo + CZ(1235) + 00)
    # Python si poradí s obřími čísly automaticky
    check_str = f"{bank_code}{prefix}{number}123500"
    
    remainder = int(check_str) % 97
    check_digits = str(98 - remainder).zfill(2)
    
    return f"CZ{check_digits}{bank_code}{prefix}{number}"

# --- FUNKCE PRO EXTRAKCI TEXTU Z PDF ---
def extract_text_from_pdf(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.error(f"Chyba při čtení PDF: {e}")
    return text

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="DIP QR Generátor v31", layout="centered")

# CSS pro hezčí vzhled v Dark i Light módu
st.markdown("""
    <style>
    .stTextInput, .stSelectbox { border-radius: 10px; }
    .stAlert { border-radius: 15px; }
    </style>
    """, unsafe_allow_name_with_custom_tag=True)

st.title("🎯 DIP QR Generátor")

# Inicializace stavu
if 'cached_text' not in st.session_state:
    st.session_state.cached_text = ""

# --- 1. NAHRÁVÁNÍ ---
uploaded_file = st.file_uploader("1. Nahraj PDF s instrukcemi", type="pdf")

if uploaded_file:
    # Uložíme text do session_state, aby se při každém kliknutí PDF znovu neparsovalo
    st.session_state.cached_text = extract_text_from_pdf(uploaded_file)

if st.session_state.cached_text:
    text = st.session_state.cached_text
    
    # Detekce variant A a B v textu
    has_a = "Individuální platba příspěvku zaměstnavatele na DIP" in text
    has_b = "Individuální platba příspěvku Klienta na DIP hrazená zaměstnavatelem" in text

    # --- 2. VOLBY ---
    col1, col2 = st.columns([1, 2])
    
    with col1:
        currency = st.selectbox("2. Měna", ["CZK", "USD", "EUR"])
    
    with col2:
        # Dynamicky sestavíme seznam možností
        available_options = ["Standard (Klient - SS 999)"]
        if has_a:
            available_options.append("A) Zaměstnavatel (IČO v SS)")
        if has_b:
            available_options.append("B) Zaměstnavatel (Bez SS)")
            
        payment_type = st.selectbox("3. Typ platby", available_options)

    # Specifické pole pro IČO u varianty A
    employer_ico = ""
    if "A)" in payment_type:
        employer_ico = st.text_input("4. IČO Zaměstnavatele", placeholder="Zadejte 8místné IČO")

    # --- 3. PARSOVÁNÍ DAT ---
    vs = ""
    vs_match = re.search(r'SMLOUVY[:\s]*(\d+)', text, re.IGNORECASE)
    if vs_match:
        vs = vs_match.group(1)

    account = ""
    amount = "0.00"
    ss = ""
    ks = ""

    if "Standard" in payment_type:
        ss = "999"
        # Hledáme účet podle vybrané měny
        pattern = rf'Číslo\s+účtu\s+v\s+{currency}\s*:\s*([\d\s\/-]+)'
        acc_match = re.search(pattern, text, re.IGNORECASE)
        if acc_match:
            account = re.sub(r'[^\d\/-]', '', acc_match.group(1))
            
        # Hledáme částku
        curr_label = r'(?:CZK|Kč)' if currency == 'CZK' else currency
        am_match = re.search(rf'([\d\s,.]+)\s*{curr_label}', text, re.IGNORECASE)
        if am_match:
            val = re.sub(r'[^\d,.]', '', am_match.group(1)).replace(',', '.')
            amount = f"{float(val):.2f}"
    else:
        # Varianta A nebo B
        regex_label = "Individuální\s+platba\s+příspěvku\s+zaměstnavatele\s+na\s+DIP" if "A)" in payment_type else "Individuální\s+platba\s+příspěvku\s+Klienta\s+na\s+DIP\s+hrazená\s+zaměstnavatelem"
        acc_match = re.search(rf'{regex_label}([\d\s\/-]+)', text, re.IGNORECASE)
        if acc_match:
            account = re.sub(r'[^\d\/-]', '', acc_match.group(1))
            
            if "A)" in payment_type:
                ks_m = re.search(r'IČ\s+zaměstnavatele\s+(\d{4})', text, re.IGNORECASE)
                if ks_m: ks = ks_m.group(1)
                ss = re.sub(r'\D', '', employer_ico)
            else:
                ks_m = re.search(r'NEVYPLŇOVAT\s+(\d{4})', text, re.IGNORECASE)
                if ks_m: ks = ks_m.group(1)

    # --- 4. VÝSTUP ---
    if account and vs:
        iban = cz_account_to_iban(account)
        
        # Sestavení SPAYD řetězce (s prefixy X- dle tvého zadání)
        spayd_parts = [
            "SPD*1.0",
            f"ACC:{iban}",
            f"AM:{amount}",
            f"CC:{currency}",
            f"X-VS:{vs}"
        ]
        if ks: spayd_parts.append(f"X-KS:{ks}")
        if ss: spayd_parts.append(f"X-SS:{ss}")
        
        qr_payload = "*".join(spayd_parts)

        st.divider()
        
        col_qr, col_info = st.columns([1, 1])
        
        with col_qr:
            # Generování QR pomocí Segno
            qr = segno.make(qr_payload, error='M')
            out = BytesIO()
            # scale=10 odpovídá velikosti, border=4 je standard
            qr.save(out, kind='png', scale=10, border=4)
            st.image(out.getvalue(), caption="Naskenujte v aplikaci banky")
            
        with col_info:
            st.success("Data byla úspěšně načtena")
            st.metric("IBAN (CZ04)", iban[:4] + " " + iban[4:8] + "...")
            st.write(f"**Variabilní symbol:** {vs}")
            st.write(f"**Částka:** {amount} {currency}")
            if ss: st.write(f"**Specifický symbol:** {ss}")
            if ks: st.write(f"**Konstantní symbol:** {ks}")
            
        with st.expander("Technické detaily (SPAYD řetězec)"):
            st.code(qr_payload)
            
    elif uploaded_file:
        st.error("⚠️ Nepodařilo se najít potřebné údaje (číslo účtu nebo VS). Zkuste jiný typ platby nebo měnu.")

else:
    st.info("👋 Vítejte! Nahrajte PDF soubor s instrukcemi k platbě DIP a já vám vygeneruji QR kód.")