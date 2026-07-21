import sqlite3
import pandas as pd
import streamlit as st
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="Futebol Analytics",
    page_icon="⚽",
    layout="wide"
)

DB_NAME = "futebol.db"

@st.cache_data
def load_teams():
    """Carrega a lista de times do banco SQLite."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT id, name, tla FROM teams ORDER BY name ASC", conn)
    conn.close()
    return df

@st.cache_data
def load_top_players(limit=20):
    """Carrega o ranking de jogadores."""
    conn = sqlite3.connect(DB_NAME)
    query = f"""
        SELECT p.name AS Jogador, p.position AS Posição, t.name AS Time, 
               p.rating_league AS "Nota Liga", p.rating_global AS "Nota Global"
        FROM players p
        JOIN teams t ON p.team_id = t.id
        ORDER BY p.rating_global DESC
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_team_squad(team_id):
    """Retorna os jogadores de um time específico."""
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT name AS Jogador, position AS Posição, nationality AS Nacionalidade, 
               rating_league AS "Nota Liga", rating_global AS "Nota Global"
        FROM players
        WHERE team_id = ?
        ORDER BY rating_global DESC
    """
    df = pd.read_sql_query(query, conn, params=(team_id,))
    conn.close()
    return df

def get_team_power(team_id):
    """Calcula a força média do time."""
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT AVG(rating_global) as power FROM players WHERE team_id = ?"
    df = pd.read_sql_query(query, conn, params=(team_id,))
    conn.close()
    power = df["power"].iloc[0]
    return round(power, 2) if power else 70.0

def simulate_match(home_id, home_name, away_id, away_name):
    """Simula o confronto entre dois times."""
    home_power = get_team_power(home_id)
    away_power = get_team_power(away_id)

    effective_home_power = home_power + 2.5
    base_expected_goals = 1.35
    power_diff = (effective_home_power - away_power) / 10.0

    lambda_home = max(0.2, base_expected_goals + (power_diff * 0.4))
    lambda_away = max(0.2, base_expected_goals - (power_diff * 0.4))

    home_goals = int(np.random.poisson(lambda_home))
    away_goals = int(np.random.poisson(lambda_away))

    return home_power, away_power, home_goals, away_goals

# --- INTERFACE GRÁFICA ---

st.title("⚽ Futebol Analytics & Simulator")
st.markdown("Painel de análise de desempenho de jogadores e simulador probabilístico de partidas.")

# Criação de abas para navegação
tab1, tab2, tab3 = st.tabs(["🎮 Simulador de Partidas", "🏆 Ranking Global", "📋 Elencos dos Times"])

# ABAS 1: SIMULADOR DE PARTIDAS
with tab1:
    st.header("Simular Confronto")
    teams_df = load_teams()
    
    col1, col2 = st.columns(2)
    
    with col1:
        home_team = st.selectbox("Selecione o Time Mandante (Casa):", teams_df["name"], index=0)
        home_id = int(teams_df[teams_df["name"] == home_team]["id"].iloc[0])
        
    with col2:
        # Seleciona o segundo time como padrão diferente do primeiro
        default_away_index = 1 if len(teams_df) > 1 else 0
        away_team = st.selectbox("Selecione o Time Visitante (Fora):", teams_df["name"], index=default_away_index)
        away_id = int(teams_df[teams_df["name"] == away_team]["id"].iloc[0])

    if home_id == away_id:
        st.warning("⚠️ Escolha dois times diferentes para realizar a simulação.")
    else:
        if st.button("🚀 Simular Partida", type="primary"):
            home_power, away_power, home_goals, away_goals = simulate_match(
                home_id, home_team, away_id, away_team
            )

            st.divider()
            
            # Placar visual
            res_col1, res_col2, res_col3 = st.columns([2, 1, 2])
            
            with res_col1:
                st.metric(label=f"🏠 {home_team}", value=f"{home_goals} Gol(s)", delta=f"Força: {home_power}")
                
            with res_col2:
                st.markdown("<h2 style='text-align: center; margin-top: 10px;'>VS</h2>", unsafe_allow_html=True)
                
            with res_col3:
                st.metric(label=f"✈️ {away_team}", value=f"{away_goals} Gol(s)", delta=f"Força: {away_power}")

# ABA 2: RANKING GLOBAL
with tab2:
    st.header("Top Jogadores do Mundo")
    top_n = st.slider("Quantidade de jogadores no ranking:", 5, 50, 20)
    df_top = load_top_players(top_n)
    st.dataframe(df_top, use_container_width=True)

# ABA 3: ELENCOS
with tab3:
    st.header("Consultar Elenco por Time")
    selected_team = st.selectbox("Escolha um time para ver o elenco:", teams_df["name"])
    if selected_team:
        t_id = int(teams_df[teams_df["name"] == selected_team]["id"].iloc[0])
        squad_df = get_team_squad(t_id)
        st.subheader(f"Elenco do {selected_team} ({len(squad_df)} Jogadores)")
        st.dataframe(squad_df, use_container_width=True)