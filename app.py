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

st.set_page_config(page_title="Conseq QR Automat", layout="wide")
st.title("🏦 Conseq QR Automat")

# --- 2. LOGIKA EXTRAKCE ---
def extract_data(pdf_file):
    # Tyto hodnoty tam budou VŽDY, pokud se nepodaří najít jiné
    res = {
        "vs": "", 
        "is_dip": False, 
        "client_czk": "6850057 / 2700", 
        "client_eur": "6850081 / 2700", 
        "emp_acc": "1388083926 / 2700"
    }
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Číslo smlouvy z první strany
            p1 = pdf.pages[0].extract_text() or ""
            vs_match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', p1)
            if vs_match: res["vs"] = vs_match.group(1)
            res["is_dip"] = "DIP" in p1 or "dlouhodobý" in p1.lower()
            
            # Zkusíme najít účty na poslední straně pro kontrolu
            lp = pdf.pages[-1].extract_text() or ""
            c_czk = re.search(r'v CZK:\s*([\d\s/]+)', lp)
            c_eur = re.search(r'v EUR:\s*([\d\s/]+)', lp)
            if c_czk: res["client_czk"] = c_czk.group(1).strip()
            if c_eur: res["client_eur"] = c_eur.group(1).strip()
    except:
        pass
    return res

# --- 3. UI ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    d = extract_data(file)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Parametry platby")
        # Výběr režimu
        mode = st.radio("Kdo platí?", 
                        ["Zaměstnanec - CZK", "Zaměstnanec - EUR", "Zaměstnavatel - Příspěvek DIP"])
        
        # Nastavení hodnot podle výběru (vždy s vyplněným účtem)
        if "Zaměstnanec - CZK" in mode:
            val_acc, val_ks, val_ss, val_curr = d["client_czk"], "", "999", "CZK"
        elif "Zaměstnanec - EUR" in mode:
            val_acc, val_ks, val_ss, val_curr = d["client_eur"], "", "999", "EUR"
        else: # Zaměstnavatel
            val_acc, val_ks, val_ss, val_curr = d["emp_acc"], "3552", "", "CZK"

        # VSTUPNÍ POLE - Vždy mají hodnotu (buď z PDF nebo tu výchozí)
        final_acc = st.text_input("Číslo účtu:", value=val_acc)
        final_vs = st.text_input("Variabilní symbol (smlouva):", value=d["vs"])
        
        # U zaměstnavatele chceme IČO
        if "Zaměstnavatel" in mode:
            final_ss = st.text_input("Specifický symbol (IČO):", value=val_ss)
        else:
            final_ss = st.text_input("Specifický symbol:", value=val_ss)
            
        final_ks = st.text_input("Konstantní symbol:", value=val_ks)
        final_amt = st.number_input(f"Částka ({val_curr}):", value=0.0)

    with col2:
        st.subheader("Generování")
        if final_acc and "/" in final_acc:
            if st.button("VYGENEROVAT QR KÓD"):
                try:
                    acc_p, bank_p = final_acc.split("/")
                    iban = czech_to_iban(acc_p.strip(), bank_p.strip())
                    
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(final_amt)}*CC:{val_curr}*X-VS:{final_vs}"
                    if final_ss: payload += f"*X-SS:{final_ss}"
                    if final_ks: payload += f"*X-KS:{final_ks}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=10)
                    st.image(out)
                    st.success(f"QR kód připraven pro {val_curr}")
                except Exception as e:
                    st.error(f"Chyba: {e}")
