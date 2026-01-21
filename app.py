import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


# --- Page Config ---
st.set_page_config(page_title="MMA Lab AI", page_icon="🧠", layout="wide")

# --- 🔐 Secrets Check ---
if "gcp_service_account" not in st.secrets:
    st.error("❌ შეცდომა: Google Sheets-ის გასაღები (Secrets) ვერ ვიპოვე!")
    st.stop()

if "GEMINI_API_KEY" not in st.secrets:
    st.warning("⚠️ გაფრთხილება: Gemini API Key არ არის შეყვანილი Secrets-ში. AI ანალიზი არ იმუშავებს.")

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
    url = f'https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal'
    try:
        response = requests.get(url)
        return response.json() if response.status_code == 200 else []
    except: return []

def get_ai_analysis(fight_text, odds_info):
    """Gemini AI ანალიზი"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key: return "გთხოვთ ჩაწეროთ Gemini API Key Secrets-ში."
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are an expert UFC betting analyst. Analyze: {fight_text} (Odds: {odds_info}).
    Focus on: Age, Wrestling, Chin, Cardio.
    Output:
    1. **Winner Prediction:** [Name]
    2. **Probability:** [0-100]%
    3. **Key Reason:** [1 sentence]
    4. **Value Bet?** [Yes/No]
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# --- Main App ---
def main():
    st.title("🥊 MMA Lab 3.0 - AI ACTIVE") # <--- თუ ეს არ წერია, ძველი ვერსიაა!

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
            st.session_state['ufc_data'] = fetch_ufc_events()
            if not st.session_state['ufc_data']:
                st.warning("ვერ დავუკავშირდი Odds API-ს (ან ლიმიტი ამოიწურა).")
        
        ufc_data = st.session_state.get('ufc_data', [])
        
        # 2. არჩევა
        fight_list = ["-- აირჩიე სიიდან --"] + [f"{x['home_team']} vs {x['away_team']}" for x in ufc_data]
        selected_fight = st.selectbox("აირჩიე ბრძოლა:", fight_list)

        odds_val = 2.0
        
        if selected_fight != "-- აირჩიე სიიდან --":
            # AI ღილაკი
            if st.button("✨ ჯემინაი, რას ფიქრობ?"):
                with st.spinner("AI აანალიზებს..."):
                    res = get_ai_analysis(selected_fight, "Check live odds")
                    st.info(res)
            
            # კუშის პოვნა (ავტომატური)
            fight_obj = next((x for x in ufc_data if f"{x['home_team']} vs {x['away_team']}" == selected_fight), None)
            if fight_obj:
                try: odds_val = fight_obj['bookmakers'][0]['markets'][0]['outcomes'][0]['price']
                except: pass

        st.markdown("---")
        st.subheader("📝 ბეთის შენახვა")
        
        with st.form("save_bet"):
            f_event = st.text_input("Event", value="UFC Fight Night" if selected_fight == "-- აირჩიე სიიდან --" else "UFC")
            f_fight = st.text_input("Fight", value="" if selected_fight == "-- აირჩიე სიიდან --" else selected_fight)
            f_pick = st.text_input("შენი არჩევანი")
            f_odds = st.number_input("კუში", value=float(odds_val))
            f_stake = st.number_input("თანხა (GEL)", value=10.0)
            
            if st.form_submit_button("შენახვა"):
                if sheet:
                    # მარტივი შენახვა
                    row = [f_event, f_fight, f_pick, "AI-App", f_odds, 0, 0, 0, f_stake, "", "", "", datetime.now().strftime("%Y-%m-%d"), "AI"]
                    sheet.append_row(row)
                    st.success("შენახულია!")
                    st.rerun()

    # --- Dashboard ---
    if not df.empty:
        st.write("### 📊 შენი სტატისტიკა")
        st.dataframe(df)

if __name__ == "__main__":
    main()
