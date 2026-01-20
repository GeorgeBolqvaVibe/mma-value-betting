
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="MMA Value Betting Lab", page_icon="🥊", layout="wide")

# --- Authentication & Connection ---
def get_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    if "gcp_service_account" not in st.secrets:
        st.error("Secrets not found!")
        st.stop()
        
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # სახელი: დარწმუნდი რომ ემთხვევა შენს Google Sheet-ს
    sheet = client.open("MMA_Betting_App_DB").sheet1 
    data = sheet.get_all_records()
    return sheet, data

# --- Main App ---
def main():
    st.title("🥊 MMA Value Betting Lab 2.0")
    st.markdown("### *Professional Betting Tracker & Analytics*")

    try:
        sheet, data = get_data()
        df = pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

    # --- Sidebar: Add New Bet ---
    with st.sidebar:
        st.header("➕ Add New Bet")
        with st.form("bet_form"):
            event = st.text_input("Event (e.g., UFC 324)")
            fight = st.text_input("Fight (e.g., Topuria vs Volkanovski)")
            # შეცვლილი: Fighter-ის ნაცვლად Bet Selection
            selection = st.text_input("Bet Selection (Fighter, Over/Under, Prop)")
            bookie = st.selectbox("Bookie", ["Adjarabet", "Bet365", "Crystalbet", "Pinnacle", "Leaderbet", "Other"])
            odds = st.number_input("Odds (Decimal)", min_value=1.01, step=0.01, value=2.00)
            my_prob = st.slider("My Probability %", 0, 100, 50)
            bet_amount = st.number_input("Bet Amount (GEL)", min_value=1.0, step=1.0, value=10.0)
            notes = st.text_area("Notes (Strategy)")
            
            submitted = st.form_submit_button("Add Bet 🚀")
            
            if submitted:
                if not event or not fight or not selection:
                    st.warning("Please fill all fields!")
                else:
                    implied_prob = round((1 / odds) * 100, 2)
                    ev = round(((my_prob / 100 * odds) - 1) * 100, 2)
                    date_added = datetime.now().strftime("%Y-%m-%d")
                    
                    # ახალი ხაზი (14 სვეტი)
                    new_row = [event, fight, selection, bookie, odds, implied_prob, my_prob, ev, bet_amount, "", "", "", date_added, notes]
                    sheet.append_row(new_row)
                    st.success(f"Bet added! Value Edge: {ev}%")
                    st.rerun()

    # --- Auto-Calculate Results Logic ---
    # ეს ამოწმებს, თუ Result წერია (1 ან 0), მაგრამ P&L ცარიელია, დაითვლის ავტომატურად
    if not df.empty:
        updates_needed = []
        for i, row in df.iterrows():
            res = str(row.get('Result', '')).strip()
            pl = str(row.get('Profit_Loss', '')).strip()
            
            if res in ['1', '0', '1.0', '0.0'] and pl == "":
                # გამოთვლა
                odds_val = float(row['Odds'])
                bet_val = float(row['Bet_Amount'])
                my_prob_val = float(row['My_Prob']) / 100
                result_val = float(res)
                
                # Profit/Loss
                if result_val == 1:
                    new_pl = round(bet_val * (odds_val - 1), 2)
                else:
                    new_pl = round(-bet_val, 2)
                
                # Brier Score: (Prob - Outcome)^2
                brier = round((my_prob_val - result_val) ** 2, 4)
                
                # Google Sheet-ის განახლება (Row + 2 იმიტომ რომ DataFrame 0-დან იწყება, Sheet კი 1-დან + Header)
                # სვეტი K (11) არის P&L, L (12) არის Brier
                sheet.update_cell(i + 2, 11, new_pl) 
                sheet.update_cell(i + 2, 12, brier)
                updates_needed.append(True)
        
        if any(updates_needed):
            st.toast("Results auto-calculated & synced! 🔄")
            st.rerun()

    # --- Dashboard ---
    if not df.empty:
        # Data Cleaning for Metrics
        df['Profit_Loss'] = pd.to_numeric(df['Profit_Loss'], errors='coerce').fillna(0)
        df['Bet_Amount'] = pd.to_numeric(df['Bet_Amount'], errors='coerce').fillna(0)
        df['Brier_Score'] = pd.to_numeric(df['Brier_Score'], errors='coerce') # Brier შეიძლება იყოს NaN
        
        # Metrics
        total_bets = len(df)
        completed_df = df[df['Result'] != ""]
        
        profit = df['Profit_Loss'].sum()
        roi = (profit / df['Bet_Amount'].sum() * 100) if df['Bet_Amount'].sum() > 0 else 0
        
        # Win Rate
        wins = len(completed_df[completed_df['Result'].astype(str).isin(['1', '1.0'])])
        finished_count = len(completed_df)
        win_rate = (wins / finished_count * 100) if finished_count > 0 else 0
        
        # Avg Brier Score (რაც დაბალია, უკეთესია)
        avg_brier = df['Brier_Score'].mean()

        # Cards
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Bets", total_bets)
        col2.metric("Total P&L", f"{profit:.2f} ₾", delta_color="normal")
        col3.metric("ROI", f"{roi:.1f}%")
        col4.metric("Win Rate", f"{win_rate:.1f}%")
        col5.metric("Accuracy (Brier)", f"{avg_brier:.3f}" if pd.notnull(avg_brier) else "-")

        st.markdown("---")
        
        # Tabs
        tab1, tab2 = st.tabs(["📊 Live Data", "📈 Analytics"])
        
        with tab1:
            # სვეტების სახელების გალამაზება მხოლოდ ჩვენებისთვის (Sheet-ში იგივე რჩება)
            display_df = df.rename(columns={
                'Implied_Prob': 'Market %',
                'My_Prob': 'My %',
                'EV': 'Edge %',
                'Bet_Amount': 'Wager',
                'Profit_Loss': 'P&L'
            })
            st.dataframe(display_df, use_container_width=True)
        
        with tab2:
            if not completed_df.empty:
                col_a, col_b = st.columns(2)
                
                # Bankroll Growth
                df['Cumulative_PL'] = df['Profit_Loss'].cumsum()
                fig_line = px.line(df, y='Cumulative_PL', title='💰 Bankroll Growth', markers=True)
                col_a.plotly_chart(fig_line, use_container_width=True)
                
                # Brier Score Distribution
                fig_hist = px.histogram(df, x='Brier_Score', title='🎯 Forecast Accuracy (Lower is Better)', nbins=10)
                col_b.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.info("No completed bets yet. Add results in Google Sheets (1=Win, 0=Loss) to see charts.")

    else:
        st.info("👈 Add your first bet to start tracking!")

if __name__ == "__main__":
    main()
