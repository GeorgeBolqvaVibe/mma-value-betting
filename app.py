import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import uuid
import requests  # ეს გვჭირდება API-სთვის

# --- Page Config ---
st.set_page_config(page_title="MMA Value Betting Lab Pro", page_icon="🥊", layout="wide")

# --- Classes ---
class Bet:
    def __init__(self, event, fight, fighter, bookie, odds, implied_prob, my_prob, ev, bet_amount, result, profit_loss, brier_score, date):
        self.id = str(uuid.uuid4())
        self.event = event
        self.fight = fight
        self.fighter = fighter
        self.bookie = bookie
        self.odds = odds
        self.implied_prob = implied_prob
        self.my_prob = my_prob
        self.ev = ev
        self.bet_amount = bet_amount
        self.result = result
        self.profit_loss = profit_loss
        self.brier_score = brier_score
        self.date = date

class BettingTracker:
    def __init__(self):
        if 'bets' not in st.session_state:
            st.session_state.bets = []

    def add_bet(self, bet):
        st.session_state.bets.append(bet)

    def get_dataframe(self):
        if not st.session_state.bets:
            return pd.DataFrame(columns=['Event', 'Fight', 'Fighter', 'Bookie', 'Odds', 'Implied_Prob', 'My_Prob', 'EV', 'Bet_Amount', 'Result', 'Profit_Loss', 'Brier_Score', 'Date'])
        
        data = []
        for bet in st.session_state.bets:
            data.append({
                'Event': bet.event,
                'Fight': bet.fight,
                'Fighter': bet.fighter,
                'Bookie': bet.bookie,
                'Odds': bet.odds,
                'Implied_Prob': bet.implied_prob,
                'My_Prob': bet.my_prob,
                'EV': bet.ev,
                'Bet_Amount': bet.bet_amount,
                'Result': bet.result,
                'Profit_Loss': bet.profit_loss,
                'Brier_Score': bet.brier_score,
                'Date': bet.date
            })
        return pd.DataFrame(data)

# --- API Helper Functions ---
def fetch_ufc_odds(api_key):
    """The Odds API-დან მოაქვს UFC-ის მონაცემები"""
    # ვიყენებთ MMA (Mixed Martial Arts) endpoint-ს
    sport_key = 'mma_mixed_martial_arts' 
    regions = 'eu' # ვიყენებთ ევროპულ ბუკმეიკერებს (Pinnacle შედის აქ)
    markets = 'h2h' # Head to head (მოგებაზე)
    odds_format = 'decimal'
    
    url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={api_key}&regions={regions}&markets={markets}&oddsFormat={odds_format}'
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching data: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

def process_api_data(data):
    """ამუშავებს JSON მონაცემებს მარტივ სტრუქტურაში"""
    fights_list = []
    
    for event in data:
        # მხოლოდ UFC-ის ივენთები (ზოგჯერ სხვა ლიგებიც ერევა ხოლმე)
        # The Odds API-ში ხანდახან 'UFC' პირდაპირ წერია სათაურში
        event_name = event.get('commence_time', '').split('T')[0] + " | " + event.get('home_team') + " vs " + event.get('away_team')
        
        # ვიპოვოთ საუკეთესო კოეფიციენტები (მაგალითად Pinnacle ან Unibet)
        home_odd = 0
        away_odd = 0
        bookie_name = "N/A"
        
        # ვეძებთ პირველ ხელმისაწვდომ ბუკმეიკერს კოეფიციენტებისთვის
        if event.get('bookmakers'):
            # ვცდილობთ ვიპოვოთ Pinnacle ან Unibet, თუ არა და ვიღებთ პირველს
            bookie = event['bookmakers'][0] 
            for b in event['bookmakers']:
                if b['key'] == 'pinnacle': # Pinnacle is the sharpest
                    bookie = b
                    break
            
            bookie_name = bookie['title']
            outcomes = bookie['markets'][0]['outcomes']
            
            for outcome in outcomes:
                if outcome['name'] == event['home_team']:
                    home_odd = outcome['price']
                elif outcome['name'] == event['away_team']:
                    away_odd = outcome['price']
        
        fights_list.append({
            "display_name": event_name,
            "home_fighter": event.get('home_team'),
            "away_fighter": event.get('away_team'),
            "home_odd": home_odd,
            "away_odd": away_odd,
            "bookie": bookie_name,
            "raw_data": event
        })
    
    return fights_list

# --- Main App Logic ---
tracker = BettingTracker()

st.sidebar.title("⚙️ Settings")
api_key = st.sidebar.text_input("🔑 Enter API Key (The Odds API)", type="password")
fetch_btn = st.sidebar.button("🔄 Load UFC Data")

if 'api_data' not in st.session_state:
    st.session_state.api_data = []

if fetch_btn and api_key:
    with st.spinner("Fetching latest UFC odds..."):
        raw_data = fetch_ufc_odds(api_key)
        st.session_state.api_data = process_api_data(raw_data)
        st.sidebar.success(f"Loaded {len(st.session_state.api_data)} fights!")

st.title("🥊 MMA Value Betting Lab 2.0 (SaaS Edition)")
st.markdown("_Professional Betting Tracker with Live Odds Integration_")

# Tabs
tab1, tab2 = st.tabs(["📝 Add Bet / Tracker", "📊 Analytics Dashboard"])

with tab1:
    # Input Mode Selection
    input_mode = st.radio("Input Mode:", ["⚡ Auto (Live API)", "✍️ Manual Entry"], horizontal=True)
    
    with st.form("bet_form"):
        st.subheader("New Bet Entry")
        
        # ცვლადების ინიციალიზაცია
        event_val = ""
        fight_val = ""
        fighter_val = ""
        bookie_val = "Adjarabet" # Default
        odds_val = 1.0
        
        if input_mode == "⚡ Auto (Live API)" and st.session_state.api_data:
            # Dropdown ივენთებისთვის
            fight_options = [f['display_name'] for f in st.session_state.api_data]
            selected_fight_display = st.selectbox("Select Fight", options=fight_options)
            
            # არჩეული ბრძოლის მონაცემების პოვნა
            selected_fight_data = next((item for item in st.session_state.api_data if item["display_name"] == selected_fight_display), None)
            
            if selected_fight_data:
                event_val = "UFC / MMA" # API-დან ზუსტი ივენთის სახელი რთულია, იყოს ზოგადი ან თარიღი
                fight_val = f"{selected_fight_data['home_fighter']} vs {selected_fight_data['away_fighter']}"
                
                # მებრძოლის არჩევა
                fighter_selection = st.radio("Select Fighter", [selected_fight_data['home_fighter'], selected_fight_data['away_fighter']], horizontal=True)
                fighter_val = fighter_selection
                
                # კოეფიციენტის ავტომატური შევსება
                if fighter_selection == selected_fight_data['home_fighter']:
                    odds_val = selected_fight_data['home_odd']
                else:
                    odds_val = selected_fight_data['away_odd']
                
                st.info(f"💡 Best Odds found on **{selected_fight_data['bookie']}**: {odds_val}")
                bookie_val = st.text_input("Bookie", value=selected_fight_data['bookie']) # უფლება მივცეთ შეცვალოს
                
        else:
            # Manual Mode
            c1, c2 = st.columns(2)
            event_val = c1.text_input("Event (e.g., UFC 300)")
            fight_val = c2.text_input("Fight (e.g., Gaethje vs Holloway)")
            fighter_val = c1.text_input("Fighter Selection")
            bookie_val = c2.selectbox("Bookie", ["Adjarabet", "Crystalbet", "Betlive", "Pinnacle", "Other"])

        # Common Inputs
        c3, c4, c5 = st.columns(3)
        # თუ API-დანაა, odds_val უკვე შევსებულია
        odds = c3.number_input("Decimal Odds", min_value=1.0, value=float(odds_val), step=0.01)
        my_prob = c4.number_input("My Probability (%)", min_value=0.0, max_value=100.0, value=50.0)
        stake = c5.number_input("Stake Amount (GEL)", min_value=1.0, value=10.0)

        # Calculations (Real-time update logic isn't perfect in forms, but works on submit)
        implied = round((1/odds) * 100, 2) if odds > 0 else 0
        ev = round(((my_prob/100) * (odds - 1)) - ((1 - (my_prob/100)) * 1), 2) * 100
        
        st.caption(f"Implied Probability: {implied}% | **Expected Value (EV): {ev}%**")

        # Results (Optional at entry)
        result = st.selectbox("Result (Update later if pending)", ["Pending", "Win", "Loss", "Void"])
        
        submitted = st.form_submit_button("Add Bet to Tracker")
        
        if submitted:
            pnl = 0
            brier = 0
            if result == "Win":
                pnl = (stake * odds) - stake
                brier = ( (my_prob/100) - 1 ) ** 2
            elif result == "Loss":
                pnl = -stake
                brier = ( (my_prob/100) - 0 ) ** 2
                
            new_bet = Bet(event_val, fight_val, fighter_val, bookie_val, odds, implied, my_prob, ev, stake, result, pnl, brier, datetime.now())
            tracker.add_bet(new_bet)
            st.success(f"Bet Added! {fighter_val} @ {odds}")

    # Display Data
    st.divider()
    df = tracker.get_dataframe()
    if not df.empty:
        st.dataframe(df.sort_values(by='Date', ascending=False), use_container_width=True)
        
        # Edit/Delete logic could be added here
    else:
        st.info("No bets tracked yet. Add one above!")

with tab2:
    st.subheader("Performance Analytics")
    df = tracker.get_dataframe()
    
    if not df.empty:
        # KPI Cards
        total_bets = len(df)
        total_pnl = df['Profit_Loss'].sum()
        roi = (total_pnl / df['Bet_Amount'].sum()) * 100 if df['Bet_Amount'].sum() > 0 else 0
        win_rate = (len(df[df['Result']=='Win']) / len(df[df['Result'].isin(['Win', 'Loss'])])) * 100 if len(df[df['Result'].isin(['Win', 'Loss'])]) > 0 else 0
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Bets", total_bets)
        k2.metric("Total P&L", f"{total_pnl:.2f} ₾", delta_color="normal")
        k3.metric("ROI", f"{roi:.1f}%")
        k4.metric("Win Rate", f"{win_rate:.1f}%")
        
        # Charts
        st.divider()
        
        # 1. Cumulative Profit
        df['Cumulative_PL'] = df['Profit_Loss'].cumsum()
        fig_pnl = px.line(df.reset_index(), x='index', y='Cumulative_PL', title='Bankroll Growth Over Time', markers=True)
        st.plotly_chart(fig_pnl, use_container_width=True)
        
        # 2. EV vs Actual
        fig_ev = px.scatter(df, x='EV', y='Profit_Loss', color='Result', size='Bet_Amount', hover_data=['Fighter'], title='EV vs Actual Result')
        st.plotly_chart(fig_ev, use_container_width=True)
        
    else:
        st.warning("Add bets to see analytics.")
