import streamlit as st
import pandas as pd
import requests
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="MMA Value Lab Pro", page_icon="🥊", layout="wide")

# --- 🔐 Secrets Check ---
if "gcp_service_account" not in st.secrets or "GEMINI_API_KEY" not in st.secrets:
    st.error("❌ Secrets (API Key ან Google Sheet) ვერ ვიპოვე!")
    st.stop()

# --- Functions ---
@st.cache_resource
def get_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("MMA_Betting_App_DB").sheet1 
    except: return None

@st.cache_data(ttl=3600) # კეშირება 1 საათით, რომ ყოველ ჯერზე არ აწვალოს API
def fetch_ufc_events():
    api_key = st.secrets.get("ODDS_API_KEY")
    if not api_key: return []
    url = f'https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/?apiKey={api_key}&regions=eu&markets=h2h&oddsFormat=decimal'
    try:
        response = requests.get(url)
        return response.json() if response.status_code == 200 else []
    except: return []

def get_ai_analysis(fight_name, fight_data_json):
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    ROLE: Expert MMA Handicapper & Data Scientist.
    TONE: Direct, Analytical, Professional. NO greetings, NO "As an AI", NO mentioning "API data".
    LANGUAGE: Georgian (ქართული).
    
    TASK: Analyze {fight_name} based on the provided JSON data: {fight_data_json}.
    
    CRITICAL INSTRUCTION: Analyze strictly considering the WEIGHT CLASS specifics (e.g., Heavyweight = Chin/Power implies volatility; Flyweight = Cardio/Volume is key).
    
    OUTPUT FORMAT (Use Markdown Table):
    
    ### 1. 10-Point System Breakdown
    | # | კრიტერიუმი | {fight_name.split('vs')[0]} | {fight_name.split('vs')[1]} | შენიშვნა |
    |---|---|---|---|---|
    | 1 | **სტრაიკინგი (Tech & Power)** | [0-10] | [0-10] | |
    | 2 | **გრეპლინგი (Offense/BJJ)** | [0-10] | [0-10] | |
    | 3 | **ჭიდაობის დაცვა (TDD)** | [0-10] | [0-10] | |
    | 4 | **გამძლეობა (Chin)** | [0-10] | [0-10] | |
    | 5 | **კარდიო (Gas Tank)** | [0-10] | [0-10] | |
    | 6 | **ასაკი & ცვეთა** | [0-10] | [0-10] | |
    | 7 | **ფიზიკა (Reach/Height)** | [0-10] | [0-10] | |
    | 8 | **Fight IQ** | [0-10] | [0-10] | |
    | 9 | **აქტიურობა (Rust)** | [0-10] | [0-10] | |
    | 10| **ოპოზიციის დონე** | [0-10] | [0-10] | |
    | **Σ** | **ჯამური რეიტინგი (100)** | **[SUM]** | **[SUM]** | |

    ### 2. ანალიტიკური დასკვნა
    (დაწერე 2-3 მკაფიო წინადადება. რატომ იგებს ერთი? გაითვალისწინე წონის სპეციფიკა).

    ### 3. ვერდიქტი
    *   **პროგნოზი:** [სახელი]
    *   **მეთოდი:** [KO/Sub/Decision]
    *   **Fair Odds (შენი კუში):** [მაგ: 1.50]
    *   **Value:** [კი/არა] (თუ შენი კუში < ბუქმეიქერის კუშზე)
    """
    
    try:
        return model.generate_content(prompt).text
    except Exception as e: return f"Error: {e}"

# --- Main Logic ---
def main():
    st.title("🥊 MMA Value Lab")

    # 1. ავტომატური ჩატვირთვა (აღარ სჭირდება ღილაკზე დაჭერა)
    if 'ufc_data' not in st.session_state:
        with st.spinner("ბაზრის მონაცემების ჩატვირთვა..."):
            st.session_state['ufc_data'] = fetch_ufc_events()

    ufc_data = st.session_state.get('ufc_data', [])
    sheet = get_google_sheet()
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("პარამეტრები")
        if st.button("🔄 მონაცემების განახლება"): # იძულებითი განახლება
            st.cache_data.clear()
            st.session_state['ufc_data'] = fetch_ufc_events()
            st.rerun()

        # ბრძოლის არჩევა
        fight_map = {f"{x['home_team']} vs {x['away_team']}": x for x in ufc_data}
        fight_options = ["-- აირჩიე --"] + list(fight_map.keys())
        selected_fight_name = st.selectbox("აირჩიე ბრძოლა:", fight_options)
        
        selected_fight_obj = fight_map.get(selected_fight_name)
        
        # ავტომატური კოეფიციენტების ამოღება
        home_odds, away_odds = 0.0, 0.0
        bookie_name = "N/A"
        
        if selected_fight_obj:
            try:
                # ვიღებთ პირველ ხელმისაწვდომ კუშებს
                markets = selected_fight_obj['bookmakers'][0]['markets'][0]['outcomes']
                bookie_name = selected_fight_obj['bookmakers'][0]['title']
                for m in markets:
                    if m['name'] == selected_fight_obj['home_team']: home_odds = m['price']
                    elif m['name'] == selected_fight_obj['away_team']: away_odds = m['price']
            except: pass

        # AI ღილაკი
        if selected_fight_name != "-- აირჩიე --":
            if st.button("🧠 AI ანალიზი"):
                with st.spinner("მუშავდება..."):
                    res = get_ai_analysis(selected_fight_name, str(selected_fight_obj))
                    st.session_state['last_analysis'] = res

    # --- Main Content ---
    col1, col2 = st.columns([2, 1])

    with col1:
        if 'last_analysis' in st.session_state:
            st.markdown(st.session_state['last_analysis'])
        else:
            st.info("აირჩიეთ ბრძოლა მარცხენა მენიუდან.")

    with col2:
        if selected_fight_name != "-- აირჩიე --":
            st.subheader("ბილეთის შექმნა")
            with st.form("bet_form"):
                # ავტომატური არჩევანი (რადიო ღილაკებით)
                pick_options = [
                    f"{selected_fight_obj['home_team']} ({home_odds})",
                    f"{selected_fight_obj['away_team']} ({away_odds})"
                ]
                selection = st.radio("ვისზე დებ?", pick_options)
                
                # კუშის ავტომატური შევსება არჩევანის მიხედვით
                chosen_odds = home_odds if selection == pick_options[0] else away_odds
                
                final_odds = st.number_input("კუში (Odds)", value=float(chosen_odds))
                stake = st.number_input("თანხა (GEL)", value=10.0, step=5.0)
                notes = st.text_area("შენიშვნა", placeholder="მაგ: Value Bet, AI recommendation...")
                
                if st.form_submit_button("💾 ბაზაში შენახვა"):
                    if sheet:
                        clean_pick = selection.split(' (')[0] # სახელს ვაცალკევებთ კუშისგან
                        row = [
                            datetime.now().strftime("%Y-%m-%d"),
                            "UFC",
                            selected_fight_name,
                            clean_pick,
                            final_odds,
                            stake,
                            "Pending",
                            "",
                            notes
                        ]
                        sheet.append_row(row)
                        st.success("შენახულია!")
                    else:
                        st.error("Sheets-თან კავშირი ვერ დამყარდა")

    # --- Stats ---
    if sheet:
        data = sheet.get_all_records()
        if data:
            st.markdown("---")
            st.markdown("### 📊 ისტორია")
            st.dataframe(pd.DataFrame(data).tail(5)) # ბოლო 5 ბეთი

if __name__ == "__main__":
    main()
