import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="MMA Lab AI Pro", page_icon="🥊", layout="wide")

# --- 🔐 Secrets Check ---
if "gcp_service_account" not in st.secrets:
    st.error("❌ შეცდომა: Google Sheets-ის გასაღები (Secrets) ვერ ვიპოვე!")
    st.stop()

if "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ გაფრთხილება: Gemini API Key არ არის შეყვანილი Secrets-ში.")

# --- Functions ---
def get_google_sheet():
    """უკავშირდება Google Sheets-ს"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("MMA_Betting_App_DB").sheet1 
        return sheet
    except Exception as e:
        st.error(f"Google Sheets Error: {e}")
        return None

def fetch_ufc_events():
    """The Odds API - UFC ბრძოლები"""
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key: return []
    # ვიყენებთ H2H მარკეტს
    url = f'https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Request failed: {e}")
        return []

def get_ai_analysis(fight_name, fight_data_json):
    """Gemini AI ანალიზი (მკაცრი 10-ქულიანი სისტემა)"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "გთხოვთ ჩაწეროთ Gemini API Key Secrets-ში."
    
    genai.configure(api_key=api_key)
    
    # ვიყენებთ 2.0 Flash-ს, რომელიც ძალიან სწრაფია და ჭკვიანი
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Prompt-ის ქართული ვერსია, მკაცრი ინსტრუქციებით
    prompt = f"""
    შენ ხარ პროფესიონალი MMA ანალიტიკოსი და Value Betting ექსპერტი.
    
    განსახილველი ბრძოლა: {fight_name}
    დამატებითი დეტალები (API Data): {fight_data_json}
    
    დავალება: გააანალიზე ეს ბრძოლა მკაცრად 10-ქულიანი სისტემით თითოეული მებრძოლისთვის.
    
    შეავსე შემდეგი ფორმატი ქართულ ენაზე:
    
    ### 1. მებრძოლების შეფასება (0-10 ქულა)
    | კრიტერიუმი | {fight_name.split('vs')[0]} (ქულა) | {fight_name.split('vs')[1]} (ქულა) | კომენტარი |
    |---|---|---|---|
    | **ასაკი & ფიზიკა** | [ქულა] | [ქულა] | [მოკლე განმარტება] |
    | **ჭიდაობა/გრეპლინგი** | [ქულა] | [ქულა] | [მოკლე განმარტება] |
    | **გამძლეობა (Chin)** | [ქულა] | [ქულა] | [მოკლე განმარტება] |
    | **კარდიო** | [ქულა] | [ქულა] | [მოკლე განმარტება] |
    | **სტრაიკინგი** | [ქულა] | [ქულა] | [მოკლე განმარტება] |
    
    ### 2. პროგნოზი
    *   **გამარჯვებული:** [სახელი]
    *   **მეთოდი:** [KO/TKO, Sub, Decision]
    *   **ალბათობა:** [0-100]%
    
    ### 3. Value Betting ვერდიქტი
    *   **Fair Odds (შენი კოეფიციენტი):** [მაგ: 1.50]
    *   **არის Value?** [კი/არა] (შეადარე მოცემულ კოეფიციენტებს თუ არის API-ში)
    *   **რჩევა:** [რაზე დავდოთ? მაგ: მოგება, რაუნდების მეტობა და ა.შ.]
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# --- Main App ---
def main():
    st.title("🥊 MMA Lab 4.0 - Georgian AI Edition")

    sheet = get_google_sheet()
    if sheet:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame()

    # --- Sidebar ---
    with st.sidebar:
        st.header("🧠 AI ანალიზატორი")
        
        # 1. განახლება
        if st.button("🔄 ბრძოლების განახლება (API)"):
            with st.spinner("ვიღებ მონაცემებს..."):
                st.session_state['ufc_data'] = fetch_ufc_events()
        
        ufc_data = st.session_state.get('ufc_data', [])
        
        # 2. არჩევა
        fight_options = ["-- აირჩიე სიიდან --"]
        if ufc_data:
            fight_options += [f"{x['home_team']} vs {x['away_team']}" for x in ufc_data]
            
        selected_fight = st.selectbox("აირჩიე ბრძოლა:", fight_options)

        # მონაცემების ამოღება არჩეული ბრძოლისთვის
        selected_fight_data = None
        odds_val = 1.0
        
        if selected_fight != "-- აირჩიე სიიდან --":
            # ვპოულობთ კონკრეტულ ობიექტს ლისტში
            for f in ufc_data:
                if f"{f['home_team']} vs {f['away_team']}" == selected_fight:
                    selected_fight_data = f
                    # ვცდილობთ კოეფიციენტის ამოღებას პირველივე ბუქმეიქერიდან
                    try: 
                        odds_val = f['bookmakers'][0]['markets'][0]['outcomes'][0]['price']
                    except: 
                        odds_val = 1.0
                    break
            
            # AI ღილაკი
            if st.button("✨ ჯემინაი, შეაფასე (10-ქულიანი)"):
                with st.spinner("AI აანალიზებს მებრძოლებს..."):
                    # აქ ვაწვდით მთლიან JSON-ს, რომ თარიღი და კოეფიციენტები დაინახოს
                    res = get_ai_analysis(selected_fight, str(selected_fight_data))
                    st.session_state['ai_result'] = res

            if 'ai_result' in st.session_state:
                st.markdown("---")
                st.markdown(st.session_state['ai_result'])

        st.markdown("---")
        st.subheader("📝 ბეთის შენახვა")
        
        with st.form("save_bet"):
            f_event = st.text_input("Event", value="UFC")
            f_fight = st.text_input("Fight", value="" if selected_fight == "-- აირჩიე სიიდან --" else selected_fight)
            f_pick = st.text_input("შენი არჩევანი")
            f_odds = st.number_input("კუში", value=float(odds_val))
            f_stake = st.number_input("თანხა (GEL)", value=10.0)
            
            if st.form_submit_button("💾 შენახვა"):
                if sheet:
                    row = [
                        datetime.now().strftime("%Y-%m-%d"), # Date
                        f_event, 
                        f_fight, 
                        f_pick, 
                        f_odds, 
                        f_stake, 
                        "Pending", # Status
                        "", # Result
                        "AI Analysis" # Notes
                    ]
                    # ყურადღება: დარწმუნდით რომ row-ს სვეტების რაოდენობა ემთხვევა შიტს
                    try:
                        sheet.append_row(row)
                        st.success("ბეთი შენახულია!")
                    except Exception as e:
                        st.error(f"შენახვის შეცდომა: {e}")

    # --- Dashboard ---
    if not df.empty:
        st.write("### 📊 შენი სტატისტიკა")
        st.dataframe(df)

if __name__ == "__main__":
    main()
