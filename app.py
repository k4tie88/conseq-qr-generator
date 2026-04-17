import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (NEPRŮSTŘELNÝ) ---
def czech_to_iban(account_number, bank_code):
    # Odstranění mezer a vyčištění
    clean_acc = account_number.replace(" ", "").replace("-", "")
    
    # Rozdělení na předčíslí a hlavní číslo (Conseq má 4+7 nebo 4+6)
    if len(clean_acc) > 10:
        prefix = clean_acc[:-10]
        acc = clean_acc[-10:]
    else:
        # Pokud je to krátké, zkusíme najít, jestli tam nebyla mezera/pomlčka dříve
        # Pro Conseq 6850 057 je prefix 6850 a acc 057
        if len(clean_acc) == 7:
            prefix = clean_acc[:4]
            acc = clean_acc[4:]
        else:
            prefix = "0"
            acc = clean_acc
            
    prefix_str = prefix.zfill(6)
    acc_str = acc.zfill(10)
    
    check_str = f"{bank_code}{prefix_str}{acc_str}123500"
    mod = int(check_str) % 97
    check_digits = 98 - mod
    return f"CZ{check_digits:02d}{bank_code}{prefix_str}{acc_str}"

st.set_page_config(page_title="Conseq QR Generátor PRO", layout="wide")
st.title("🏦 Conseq QR Generátor")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    full_text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    
    is_dip = "DIP" in full_text.upper() or "DLOUHODOBÝ INVESTIČNÍ PRODUKT" in full_text.upper()
    
    # --- NOVÉ STRIKTNÍ VYHLEDÁVÁNÍ ÚČTŮ ---
    def get_conseq_account(currency, text):
        # Hledáme label "Číslo účtu v CZK:" nebo "Číslo účtu v EUR:"
        # A bereme vše až k dalšímu labelu nebo konci řádku
        pattern = f"Číslo účtu v {currency}:\\s*([\\d\\s/-]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            # Rozdělení na číslo a kód banky (hledáme lomítko)
            if "/" in raw:
                parts = raw.split("/")
                acc_num = parts[0].strip()
                # Kód banky jsou první 4 číslice po lomítku
                bank_code = re.search(r"\d{4}", parts[1]).group(0)
                return f"{acc_num} / {bank_code}"
        return None

    acc_czk = get_conseq_account("CZK", full_text)
    acc_eur = get_conseq_account("EUR", full_text)
    
    vs_match = re.search(r'41\d{8}', full_text)
    found_vs = vs_match.group(0) if vs_match else ""

    st.divider()
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚙️ Parametry platby")
        
        # Ošetření DIPu
        if is_dip:
            st.success("✅ Detekována smlouva DIP")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec", "Zaměstnavatel - Var 1 (Příspěvek)", "Zaměstnavatel - Var 2 (Hromadná)"])
        else:
            st.warning("📄 Detekována klasická smlouva")
            rezim = st.radio("Kdo platí?", ["Zaměstnanec"])

        currency = st.selectbox("Měna platby (v tabulce):", ["CZK", "EUR"])
        
        # Výběr správného účtu
        detected_acc = acc_czk if currency == "CZK" else acc_eur
        
        if detected_acc:
            st.info(f"📍 Nalezen účet pro {currency}: **{detected_acc}**")
        else:
            st.error(f"❌ Účet pro {currency} v PDF nenalezen!")
            detected_acc = st.text_input("Zadejte účet ručně (např. 6850 057 / 2700):")

        amt = st.number_input(f"Částka ({currency}):", value=0.0, step=100.0)
        f_vs = st.text_input("Variabilní symbol (Číslo smlouvy):", value=found_vs)
        
        f_ss = "999" if rezim == "Zaměstnanec" else ""
        if rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
            f_ss = st.text_input("Zadejte IČO zaměstnavatele (pro SS):")

    with col2:
        st.subheader("📱 QR kód")
        if detected_acc and "/" in detected_acc:
            acc_p, bank_p = detected_acc.split("/")
            iban = czech_to_iban(acc_p.strip(), bank_p.strip())

            if st.button("VYGENEROVAT"):
                if "Var 1" in rezim and not f_ss:
                    st.error("Zadejte IČO!")
                else:
                    amt_fmt = "{:.2f}".format(amt)
                    payload = f"SPD*1.0*ACC:{iban}*AM:{amt_fmt}*CC:{currency}*X-VS:{f_vs}"
                    if f_ss: payload += f"*X-SS:{f_ss}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=12, border=4)
                    st.image(out)
                    
                    st.success("Kontrola údajů:")
                    st.write(f"🏦 **Bankovní účet:** {detected_acc}")
                    st.write(f"🌍 **IBAN:** `{iban}`")
                    st.write(f"💰 **Částka:** {amt_fmt} {currency}")
                    st.write(f"🔢 **VS:** {f_vs} | **SS:** {f_ss if f_ss else 'neuveden'}")