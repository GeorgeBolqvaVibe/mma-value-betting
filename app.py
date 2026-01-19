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
    
    # Secrets-ის შემოწმება
    if "gcp_service_account" not in st.secrets:
        st.error("Secrets not found! Please set up gcp_service_account in Streamlit Cloud.")
        st.stop()
        
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # დარწმუნდი, რომ Google Sheet-ს ზუსტად ეს სახელი ჰქვია!
    # თუ შენ სხვანაირად დაარქვი, აქ შეცვალე ("UFC_Betting_App_DB" -> "შენი_სახელი")
    sheet = client.open("MMA_Betting_App_DB").sheet1
    data = sheet.get_all_records()
    return sheet, data

# --- Main App ---
def main():
    st.title("🥊 MMA Value Betting Lab 2026")
    st.markdown("### *Professional Betting Tracker & Analytics*")

    try:
        sheet, data = get_data()
        df = pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        st.info("💡 Tip: Did you share the Google Sheet with your service account email?")
        st.stop()

    # --- Sidebar: Add New Bet ---
    with st.sidebar:
        st.header("➕ Add New Bet")
        with st.form("bet_form"):
            event = st.text_input("Event (e.g., UFC 324)")
            fight = st.text_input("Fight (e.g., Topuria vs Volkanovski)")
            fighter = st.text_input("Fighter (Your Pick)")
            bookie = st.selectbox("Bookie", ["Adjarabet", "Bet365", "Crystalbet", "Pinnacle", "Leaderbet"])
            odds = st.number_input("Odds (Decimal)", min_value=1.01, step=0.01)
            my_prob = st.slider("My Probability %", 0, 100, 50)
            bet_amount = st.number_input("Bet Amount (GEL)", min_value=1.0, step=1.0, value=10.0)
            notes = st.text_area("Notes (Strategy/Reasoning)")
            
            submitted = st.form_submit_button("Add Bet 🚀")
            
            if submitted:
                if not event or not fight or not fighter:
                    st.warning("Please fill in all required fields!")
                else:
                    implied_prob = round((1 / odds) * 100, 2)
                    ev = round(((my_prob / 100 * odds) - 1) * 100, 2)
                    date_added = datetime.now().strftime("%Y-%m-%d")
                    
                    # 14 სვეტი ზუსტად (როგორც Sheet-ში)
                    new_row = [event, fight, fighter, bookie, odds, implied_prob, my_prob, ev, bet_amount, "", "", "", date_added, notes]
                    sheet.append_row(new_row)
                    st.success(f"Bet on {fighter} added successfully! EV: {ev}%")
                    st.rerun()

    # --- Dashboard ---
    if not df.empty:
        # Metrics
        total_bets = len(df)
        completed_bets = df[df['Result'] != ""]
        
        # უსაფრთხო კონვერტაცია რიცხვებში (რომ არ გაჭედოს)
        df['Profit_Loss'] = pd.to_numeric(df['Profit_Loss'], errors='coerce').fillna(0)
        df['Bet_Amount'] = pd.to_numeric(df['Bet_Amount'], errors='coerce').fillna(0)
        
        profit = df['Profit_Loss'].sum()
        invested = df['Bet_Amount'].sum()
        roi = (profit / invested * 100) if invested > 0 else 0

        # Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Bets", total_bets)
        col2.metric("Total P&L", f"{profit:.2f} ₾", delta_color="normal")
        col3.metric("ROI", f"{roi:.1f}%", delta_color="normal")
        
        # Win Rate Calculation
        wins = len(df[df['Result'] == 1])
        losses = len(df[df['Result'] == 0])
        total_finished = wins + losses
        win_rate = (wins / total_finished * 100) if total_finished > 0 else 0
        col4.metric("Win Rate", f"{win_rate:.1f}%")

        # Visuals
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📊 History", "📈 Analytics"])
        
        with tab1:
            st.dataframe(df)
        
        with tab2:
            if not completed_bets.empty:
                # Cumulative Profit Chart
                df['Cumulative_PL'] = df['Profit_Loss'].cumsum()
                fig_line = px.line(df, y='Cumulative_PL', title='Bankroll Growth Over Time')
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Add results (1 for Win, 0 for Loss) in Google Sheets to see analytics!")

    else:
        st.info("👈 Add your first bet from the sidebar to get started!")

if __name__ == "__main__":
    main()
