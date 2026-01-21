import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="MMA Value Betting Lab Pro", page_icon="🥊", layout="wide")

# --- 🔐 Secrets Management ---
# დარწმუნდი, რომ Streamlit Secrets-ში გაქვს:
# 1. [gcp_service_account] - Google Sheets-ისთვის
# 2. ODDS_API_KEY - The Odds API-ისთვის
# 3. GEMINI_API_KEY - Google Gemini-ისთვის

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
    """მოაქვს UFC ბრძოლები The Odds API-დან"""
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key:
        return []
    
    url = f'https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

def get_ai_analysis(fight_text, odds_info):
    """ეკითხება Gemini-ს პროგნოზს"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Gemini API Key not found!"
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Act as a professional MMA Analyst using a 10-point scoring system (Age, Wrestling, Chin, Cardio, Activity, Streak, Damage, Finish Rate, Gym, Weight Cut).
    
    Analyze this fight: {fight_text}
    Current Odds info: {odds_info}
    
    Provide a concise response in this format:
    1. **Key Advantage:** (Who has the edge and why, 1 sentence)
    2. **Risk Factor:** (What could go wrong for the favorite)
    3. **AI Winning Probability:** (Give a specific percentage, e.g., 65%)
    4. **Value Verdict:** (Compare your % to the odds. Is it a value bet?)
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Error: {e}"

# --- Main App ---
def main():
    st.title("🥊 MMA Value Betting Lab 3.0 (AI Edition)")
    
    # მონაცემების წამოღება
    sheet = get_google_sheet()
    if sheet:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame()

    # --- Sidebar: New Bet ---
    with st.sidebar:
        st.header("⚡ Smart Bet Entry")
        
        # 1. API Data Fetch
        if st.button("🔄 Refresh Live Odds"):
            st.session_state['ufc_data'] = fetch_ufc_events()
        
        ufc_data = st.session_state.get('ufc_data', [])
        
        # 2. Fight Selection
        fight_options = ["Custom Entry"]
        if ufc_data:
            fight_options += [f"{x['home_team']} vs {x['away_team']}" for x in ufc_data]
        
        selected_fight = st.selectbox("Select Fight:", fight_options)
        
        # ცვლადები ფორმისთვის
        form_event = ""
        form_fight = ""
        form_odds = 2.0
        odds_info_str = ""

        if selected_fight != "Custom Entry":
            # მონაცემების ამოღება არჩეული ბრძოლიდან
            fight_obj = next((x for x in ufc_data if f"{x['home_team']} vs {x['away_team']}" == selected_fight), None)
            if fight_obj:
                form_event = "UFC / MMA"
                form_fight = selected_fight
                # ვეძებთ Pinnacle-ს ან ვიღებთ პირველს
                try:
                    bookmakers = fight_obj['bookmakers']
                    best_bookie = bookmakers[0]
                    for b in bookmakers:
                        if b['key'] == 'pinnacle': best_bookie = b
                    
                    # ვიღებთ პირველი მებრძოლის კუშს დეფოლტად
                    form_odds = best_bookie['markets'][0]['outcomes'][0]['price']
                    odds_info_str = f"Odds: {best_bookie['markets'][0]['outcomes'][0]['price']} vs {best_bookie['markets'][0]['outcomes'][1]['price']}"
                except:
                    pass

        # 3. AI Analysis Button
        if selected_fight != "Custom Entry" and st.button("🧠 Analyze with Gemini AI"):
            with st.spinner("AI is watching tape..."):
                analysis = get_ai_analysis(selected_fight, odds_info_str)
                st.session_state['ai_result'] = analysis

        # AI შედეგის ჩვენება
        if 'ai_result' in st.session_state:
            st.info(st.session_state['ai_result'])

        # 4. Final Form to Save
        with st.form("bet_form"):
            st.markdown("---")
            event_in = st.text_input("Event", value=form_event)
            fight_in = st.text_input("Fight", value=form_fight)
            selection_in = st.text_input("Your Pick (Fighter)", value=form_fight.split(" vs ")[0] if form_fight else "")
            
            c1, c2 = st.columns(2)
            odds_in = c1.number_input("Odds", value=float(form_odds), step=0.01)
            stake_in = c2.number_input("Stake (GEL)", value=20.0)
            
            my_prob_in = st.slider("My Confidence %", 0, 100, 55)
            
            submitted = st.form_submit_button("💾 Save to Sheet")
            
            if submitted and sheet:
                implied = round((1/odds_in)*100, 2)
                ev = round(((my_prob_in/100 * odds_in) - 1) * 100, 2)
                date_now = datetime.now().strftime("%Y-%m-%d")
                
                # Sheet-ში ჩაწერა (იგივე სტრუქტურა რაც გქონდა)
                new_row = [event_in, fight_in, selection_in, "API/Smart", odds_in, implied, my_prob_in, ev, stake_in, "", "", "", date_now, "AI Assisted"]
                sheet.append_row(new_row)
                st.success("Bet Saved!")
                st.rerun()

    # --- Dashboard Area ---
    if not df.empty:
        # ძველი დაშბორდის კოდი (P&L, Charts) უცვლელად აქ
        st.subheader("📊 Performance Dashboard")
        
        # ტიპების გასწორება
        df['Profit_Loss'] = pd.to_numeric(df['Profit_Loss'], errors='coerce').fillna(0)
        df['Bet_Amount'] = pd.to_numeric(df['Bet_Amount'], errors='coerce').fillna(0)
        
        col1, col2, col3 = st.columns(3)
        total_pl = df['Profit_Loss'].sum()
        roi = (total_pl / df['Bet_Amount'].sum() * 100) if df['Bet_Amount'].sum() > 0 else 0
        
        col1.metric("Total P&L", f"{total_pl:.2f} ₾")
        col2.metric("ROI", f"{roi:.1f}%")
        col3.metric("Total Bets", len(df))
        
        st.dataframe(df)

if __name__ == "__main__":
    main()
