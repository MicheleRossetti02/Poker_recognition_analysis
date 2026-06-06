"""
Poker GTO Dashboard - Streamlit Web Interface
Real-time session analytics and opponent profiling
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

st.set_page_config(page_title="Poker GTO Dashboard", layout="wide")

# 1. Caricamento Dati
@st.cache_data
def load_data():
    """Load session log and player database"""
    # Check if files exist
    if not os.path.exists('session_log.csv'):
        st.error("❌ session_log.csv non trovato. Esegui prima il bot per generare dati.")
        st.stop()
    
    df = pd.read_csv('session_log.csv')
    
    players = {}
    if os.path.exists('players_history.json'):
        with open('players_history.json', 'r') as f:
            players = json.load(f)
    
    return df, players

# Load data
try:
    df, players_data = load_data()
except Exception as e:
    st.error(f"Errore nel caricamento dati: {e}")
    st.info("💡 Assicurati che il bot sia stato eseguito almeno una volta per generare i file di log.")
    st.stop()

# Header
st.title("🎰 Poker GTO Bot V3 - Dashboard")
st.markdown("---")

# 2. Sidebar - Statistiche Generali
st.sidebar.title("📊 Session Summary")
st.sidebar.markdown("---")

total_hands = len(df)
if 'result_bb' in df.columns and not df['result_bb'].isna().all():
    total_profit = df['result_bb'].sum()
    avg_profit = df['result_bb'].mean()
    st.sidebar.metric("Mani Giocate", total_hands)
    st.sidebar.metric("Profitto Totale", f"{total_profit:.2f} BB")
    st.sidebar.metric("BB/100", f"{(total_profit / total_hands * 100):.2f}")
else:
    st.sidebar.metric("Mani Giocate", total_hands)
    st.sidebar.warning("⚠️ Dati di profitto non disponibili")

st.sidebar.markdown("---")
st.sidebar.info(f"👥 Giocatori tracciati: {len(players_data)}")

# 3. Grafico dei Profitti (Cumulative BB)
if 'result_bb' in df.columns and not df['result_bb'].isna().all():
    st.header("📈 Andamento Profitto")
    df['cumulative_profit'] = df['result_bb'].cumsum()
    fig_profit = px.line(
        df, 
        x=df.index, 
        y='cumulative_profit',
        title="Profitto Cumulativo in BB",
        labels={'index': 'Mani', 'cumulative_profit': 'BB Cumulative'}
    )
    fig_profit.update_traces(line_color='#00ff00', line_width=2)
    fig_profit.update_layout(
        plot_bgcolor='rgba(0,0,0,0.1)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig_profit, use_container_width=True)
else:
    st.info("💡 Inizia a giocare per vedere il grafico dei profitti!")

st.markdown("---")

# 4. Analisi Avversari
st.header("🕵️ Analisi Abitudini Avversari")

if players_data:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top Aggressors")
        # Trasforma JSON in DataFrame per visualizzazione
        p_df = pd.DataFrame.from_dict(players_data, orient='index')
        
        # Ordina per aggression_factor
        if 'aggression_factor' in p_df.columns:
            top_agg = p_df.sort_values(by='aggression_factor', ascending=False).head(10)
            fig_agg = px.bar(
                top_agg, 
                y='aggression_factor',
                title="Fattore di Aggressione per Giocatore",
                labels={'aggression_factor': 'Aggression Factor', 'index': 'Player'}
            )
            fig_agg.update_traces(marker_color='#ff6b6b')
            st.plotly_chart(fig_agg, use_container_width=True)
        else:
            st.warning("Nessun dato di aggressione disponibile")
    
    with col2:
        st.subheader("Player Stats Table")
        # Show top 10 players with most hands
        if 'hands_seen' in p_df.columns:
            top_players = p_df.sort_values(by='hands_seen', ascending=False).head(10)
            display_cols = ['hands_seen', 'aggression_factor', 'total_raises', 'total_calls', 'total_folds']
            available_cols = [col for col in display_cols if col in top_players.columns]
            st.dataframe(top_players[available_cols], use_container_width=True)
else:
    st.info("👥 Nessun giocatore tracciato ancora. Gioca alcune mani per vedere le statistiche!")

st.markdown("---")

# 5. Analisi Azioni
st.header("🎯 Frequenza Azioni")

if 'opponent_actions' in df.columns and not df['opponent_actions'].isna().all():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribuzione Azioni Avversarie")
        # Analizza la colonna opponent_actions
        # Parse actions (assuming format like "['RAISE', 'CALL']")
        all_actions = []
        for actions_str in df['opponent_actions'].dropna():
            try:
                # Try to parse as list
                if isinstance(actions_str, str):
                    actions_str = actions_str.replace("'", '"')
                    import ast
                    actions = ast.literal_eval(actions_str)
                    all_actions.extend(actions)
            except:
                pass
        
        if all_actions:
            actions_series = pd.Series(all_actions)
            action_counts = actions_series.value_counts()
            
            fig_actions = px.pie(
                values=action_counts.values,
                names=action_counts.index,
                title="Distribuzione Azioni Avversarie"
            )
            st.plotly_chart(fig_actions, use_container_width=True)
        else:
            st.info("Nessuna azione registrata ancora")
    
    with col2:
        st.subheader("Hero Decisions")
        if 'hero_decision' in df.columns and not df['hero_decision'].isna().all():
            hero_actions = df['hero_decision'].value_counts()
            fig_hero = px.bar(
                x=hero_actions.index,
                y=hero_actions.values,
                title="Distribuzione Decisioni Hero",
                labels={'x': 'Azione', 'y': 'Frequenza'}
            )
            fig_hero.update_traces(marker_color='#4ecdc4')
            st.plotly_chart(fig_hero, use_container_width=True)
else:
    st.info("💡 Dati delle azioni non ancora disponibili")

st.markdown("---")

# 6. Recent Hands
st.header("🃏 Ultime Mani")
if not df.empty:
    recent_hands = df.tail(10).sort_index(ascending=False)
    st.dataframe(recent_hands, use_container_width=True)
else:
    st.info("Nessuna mano giocata ancora")

# Footer
st.markdown("---")
st.markdown("*Dashboard aggiornata in tempo reale. Ricarica la pagina per vedere i nuovi dati.*")
