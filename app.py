import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Futebol Analytics & Match Simulator",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def get_db_connection():
    """Conecta ao banco de dados SQLite local ou cria banco em memória de fallback."""
    try:
        conn = sqlite3.connect("futebol.db", check_same_thread=False)
        # Test connection
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        if "players" in tables and "teams" in tables:
            return conn, False
    except Exception:
        pass
    
    # Fallback to in-memory database with realistic sample data if DB is missing
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    create_sample_database(conn)
    return conn, True

def create_sample_database(conn):
    """Gera uma estrutura SQLite temporária para garantir o funcionamento do dashboard."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            league_name TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            team_id INTEGER,
            name TEXT,
            position TEXT,
            nationality TEXT,
            date_of_birth TEXT,
            rating_global REAL,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        );
    """)
    
    sample_teams = [
        (1, "Arsenal FC", "Premier League"),
        (2, "Manchester City FC", "Premier League"),
        (3, "Chelsea FC", "Premier League"),
        (4, "Brentford FC", "Premier League"),
        (5, "Fulham FC", "Premier League"),
        (6, "Ipswich Town FC", "Premier League")
    ]
    cursor.executemany("INSERT INTO teams VALUES (?,?,?);", sample_teams)
    
    sample_players = [
        (101, 1, "Martin Ødegaard", "Midfield", "Norway", "1998-12-17", 91.3),
        (102, 1, "Viktor Gyökeres", "Offence", "Sweden", "1998-06-04", 87.9),
        (103, 1, "Gabriel Magalhães", "Defence", "Brazil", "1997-12-19", 88.5),
        (104, 2, "Erling Haaland", "Offence", "Norway", "2000-07-21", 94.0),
        (105, 2, "Rúben Dias", "Defence", "Portugal", "1997-05-14", 89.2),
        (106, 3, "Reece James", "Defence", "England", "1999-12-08", 89.4),
        (107, 3, "Cole Palmer", "Midfield", "England", "2002-05-06", 90.1),
        (108, 4, "Caoimhin Kelleher", "Goalkeeper", "Ireland", "1998-11-23", 89.3),
        (109, 4, "Matthew Cox", "Goalkeeper", "England", "2003-05-02", 86.9),
        (110, 5, "Sander Berge", "Midfield", "Norway", "1998-02-14", 92.8),
        (111, 6, "Dara O'Shea", "Defence", "Ireland", "1999-03-04", 99.0)
    ]
    cursor.executemany("INSERT INTO players VALUES (?,?,?,?,?,?,?);", sample_players)
    conn.commit()

def get_league_column(conn):
    """Inspeciona colunas dinamicamente para evitar erros de SQL."""
    cursor = conn.cursor()
    teams_cols = [col[1] for col in cursor.execute("PRAGMA table_info(teams)").fetchall()]
    players_cols = [col[1] for col in cursor.execute("PRAGMA table_info(players)").fetchall()]

    if "league_name" in teams_cols:
        return "t.league_name"
    elif "league" in teams_cols:
        return "t.league"
    elif "competition" in teams_cols:
        return "t.competition"
    elif "league_name" in players_cols:
        return "p.league_name"
    elif "league" in players_cols:
        return "p.league"
    return "'Liga Principal'"

conn, is_sample = get_db_connection()
league_col = get_league_column(conn)

st.title("⚽ Futebol Analytics & Match Simulator")
st.caption("Plataforma Integrada de Inteligência Esportiva e Análise Relacional SQL")

if is_sample:
    st.info("ℹ️ Exibindo modo de demonstração com dados de exemplo. Conecte seu `futebol.db` para carregar o banco completo.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🎮 Simulador de Partidas", 
    "🏆 Ranking Global", 
    "📋 Elencos dos Times", 
    "📊 SQL Analytics Lab"
])

with tab1:
    st.header("🎮 Simulador Probabilístico de Partidas")
    st.markdown("Previsão baseada no modelo estatístico da **Distribuição de Poisson** e diferencial de rating dos elencos.")
    
    # Query team ratings
    df_teams = pd.read_sql_query(f"""
        SELECT 
            t.id, 
            t.name AS clube, 
            ROUND(AVG(p.rating_global), 2) AS rating_medio,
            COUNT(p.id) as total_jogadores
        FROM teams t
        LEFT JOIN players p ON t.id = p.team_id
        GROUP BY t.id, t.name
        HAVING total_jogadores > 0
        ORDER BY rating_medio DESC
    """, conn)
    
    if not df_teams.empty:
        col_home, col_vs, col_away = st.columns([4, 1, 4])
        
        team_list = df_teams["clube"].tolist()
        
        with col_home:
            st.subheader("🏠 Time Mandante")
            home_team = st.selectbox("Escolha o Mandante", team_list, index=0, key="home_select")
            home_rating = df_teams[df_teams["clube"] == home_team]["rating_medio"].values[0]
            st.metric("Rating Médio (Mandante)", home_rating, delta="+2.5 (Fator Casa)")
            
        with col_vs:
            st.markdown("<h2 style='text-align: center; margin-top: 30px;'>VS</h2>", unsafe_allow_html=True)
            
        with col_away:
            st.subheader("✈️ Time Visitante")
            away_default_idx = 1 if len(team_list) > 1 else 0
            away_team = st.selectbox("Escolha o Visitante", team_list, index=away_default_idx, key="away_select")
            away_rating = df_teams[df_teams["clube"] == away_team]["rating_medio"].values[0]
            st.metric("Rating Médio (Visitante)", away_rating)
            
        st.divider()
        
        if st.button("▶️ Simular Partida", type="primary", use_container_width=True):
            # Poisson calculation
            home_effective = home_rating + 2.5
            diff = home_effective - away_rating
            
            lambda_home = max(0.2, 1.35 + (diff * 0.04))
            lambda_away = max(0.2, 1.35 - (diff * 0.04))
            
            home_goals = np.random.poisson(lambda_home)
            away_goals = np.random.poisson(lambda_away)
            
            st.subheader("🏆 Placar Simulado")
            col_res1, col_res2 = st.columns(2)
            col_res1.metric(home_team, f"{home_goals} Gol(s)")
            col_res2.metric(away_team, f"{away_goals} Gol(s)")
            
            # Outcome probabilities calculation
            max_g = 6
            matrix = np.zeros((max_g, max_g))
            for i in range(max_g):
                for j in range(max_g):
                    matrix[i, j] = (np.power(lambda_home, i) * np.exp(-lambda_home) / np.math.factorial(i)) * \
                                   (np.power(lambda_away, j) * np.exp(-lambda_away) / np.math.factorial(j))
            
            prob_home = np.sum(np.tril(matrix, -1)) * 100
            prob_draw = np.sum(np.diag(matrix)) * 100
            prob_away = np.sum(np.triu(matrix, 1)) * 100
            
            st.subheader("📊 Probabilidade dos Resultados")
            col_p1, col_p2, col_p3 = st.columns(3)
            col_p1.metric(f"Vitória - {home_team}", f"{prob_home:.1f}%")
            col_p2.metric("Empate", f"{prob_draw:.1f}%")
            col_p3.metric(f"Vitória - {away_team}", f"{prob_away:.1f}%")

with tab2:
    st.header("🏆 Ranking Global de Atletas")
    
    df_players_all = pd.read_sql_query(f"""
        SELECT 
            p.name AS Jogador,
            p.position AS Posição,
            p.nationality AS Nacionalidade,
            t.name AS Clube,
            {league_col} AS Liga,
            p.rating_global AS "Rating Global"
        FROM players p
        JOIN teams t ON p.team_id = t.id
        WHERE p.rating_global IS NOT NULL
        ORDER BY p.rating_global DESC
    """, conn)
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        search_name = st.text_input("🔍 Buscar por Atleta", "")
    with col_f2:
        pos_list = ["Todas"] + list(df_players_all["Posição"].dropna().unique())
        selected_pos = st.selectbox("Filtrar Posição", pos_list)
    with col_f3:
        nat_list = ["Todas"] + list(df_players_all["Nacionalidade"].dropna().unique())
        selected_nat = st.selectbox("Filtrar Nacionalidade", nat_list)
        
    filtered_df = df_players_all.copy()
    if search_name:
        filtered_df = filtered_df[filtered_df["Jogador"].str.contains(search_name, case=False, na=False)]
    if selected_pos != "Todas":
        filtered_df = filtered_df[filtered_df["Posição"] == selected_pos]
    if selected_nat != "Todas":
        filtered_df = filtered_df[filtered_df["Nacionalidade"] == selected_nat]
        
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

with tab3:
    st.header("📋 Análise Detalhada de Elencos")
    
    teams_query = pd.read_sql_query("SELECT id, name FROM teams ORDER BY name", conn)
    selected_team_name = st.selectbox("Selecione o Clube para Análise:", teams_query["name"].tolist())
    
    df_squad = pd.read_sql_query(f"""
        SELECT 
            p.name AS Jogador,
            p.position AS Posição,
            p.nationality AS Nacionalidade,
            p.date_of_birth AS "Data Nascimento",
            p.rating_global AS "Rating Global"
        FROM players p
        JOIN teams t ON p.team_id = t.id
        WHERE t.name = ?
        ORDER BY p.rating_global DESC
    """, conn, params=(selected_team_name,))
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Total de Jogadores", len(df_squad))
    col_m2.metric("Rating Médio do Elenco", f"{df_squad['Rating Global'].mean():.2f}" if not df_squad.empty else "N/A")
    col_m3.metric("Maior Rating do Time", f"{df_squad['Rating Global'].max():.1f}" if not df_squad.empty else "N/A")
    
    st.dataframe(df_squad, use_container_width=True, hide_index=True)

with tab4:
    st.header("📊 SQL Analytics Lab")
    st.markdown("""
    Execute consultas SQL avançadas (*Window Functions*, *CTEs*, *CASE WHEN*, *Agregações de Dispersão*) diretamente no banco **`futebol.db`**.
    """)
    
    # Defining SQL queries dictionary with dynamic column variable
    queries = {
        "1. Top 3 Atletas por Posição em Cada Liga (Window Functions)": f"""
-- Top 3 jogadores por posição dentro de cada liga usando DENSE_RANK()
WITH RankedPlayers AS (
    SELECT 
        p.name AS jogador,
        p.position AS posicao,
        {league_col} AS liga,
        t.name AS clube,
        p.rating_global,
        DENSE_RANK() OVER (
            PARTITION BY {league_col}, p.position 
            ORDER BY p.rating_global DESC
        ) AS ranking_posicao
    FROM players p
    JOIN teams t ON p.team_id = t.id
    WHERE p.rating_global IS NOT NULL
)
SELECT 
    liga,
    posicao,
    ranking_posicao,
    jogador,
    clube,
    rating_global
FROM RankedPlayers
WHERE ranking_posicao <= 3
ORDER BY liga, posicao, ranking_posicao;
""",
        "2. Comparativo do Elenco vs Média da Liga (CTE & Subquery)": f"""
-- Calcula o diferencial entre a média do clube e a média geral da liga
WITH LigaStats AS (
    SELECT 
        {league_col} AS liga,
        ROUND(AVG(p.rating_global), 2) AS media_liga
    FROM players p
    JOIN teams t ON p.team_id = t.id
    GROUP BY {league_col}
),
TeamStats AS (
    SELECT 
        {league_col} AS liga,
        t.name AS clube,
        COUNT(p.id) AS total_jogadores,
        ROUND(AVG(p.rating_global), 2) AS media_clube
    FROM players p
    JOIN teams t ON p.team_id = t.id
    GROUP BY {league_col}, t.name
)
SELECT 
    ts.liga,
    ts.clube,
    ts.total_jogadores,
    ts.media_clube,
    ls.media_liga,
    ROUND(ts.media_clube - ls.media_liga, 2) AS diferencial_forca
FROM TeamStats ts
JOIN LigaStats ls ON ts.liga = ls.liga
ORDER BY diferencial_forca DESC
LIMIT 10;
""",
        "3. Faixas Etárias e Maturidade Física (CASE WHEN)": """
-- Segmenta atletas por ciclo de carreira e analisa o impacto na performance
WITH PlayerAges AS (
    SELECT 
        p.id,
        p.name,
        p.rating_global,
        (CAST(strftime('%Y', 'now') AS INT) - CAST(strftime('%Y', p.date_of_birth) AS INT)) AS idade
    FROM players p
    WHERE p.date_of_birth IS NOT NULL AND p.date_of_birth != ''
)
SELECT 
    CASE 
        WHEN idade < 21 THEN '1. Promessa (< 21 anos)'
        WHEN idade BETWEEN 21 AND 23 THEN '2. Em Desenvolvimento (21-23)'
        WHEN idade BETWEEN 24 AND 29 THEN '3. Pico Performático (24-29)'
        WHEN idade BETWEEN 30 AND 34 THEN '4. Veterano Consolidado (30-34)'
        ELSE '5. Final de Carreira (35+)'
    END AS faixa_etaria,
    COUNT(id) AS quantidade_atletas,
    ROUND(AVG(idade), 1) AS idade_media,
    ROUND(AVG(rating_global), 2) AS rating_medio,
    ROUND(MAX(rating_global), 1) AS rating_maximo
FROM PlayerAges
GROUP BY faixa_etaria
ORDER BY faixa_etaria;
""",
        "4. Variância e Equilíbrio do Elenco (Análise de Dispersão)": f"""
-- Avalia a variância interna de qualidade entre os jogadores do mesmo elenco
SELECT 
    {league_col} AS liga,
    t.name AS clube,
    COUNT(p.id) AS num_jogadores,
    ROUND(AVG(p.rating_global), 2) AS rating_medio,
    ROUND(
        AVG((p.rating_global - sub.media_time) * (p.rating_global - sub.media_time)), 2
    ) AS variancia_elenco
FROM players p
JOIN teams t ON p.team_id = t.id
JOIN (
    SELECT team_id, AVG(rating_global) AS media_time
    FROM players
    GROUP BY team_id
) sub ON p.team_id = sub.team_id
GROUP BY {league_col}, t.name
HAVING num_jogadores >= 2
ORDER BY variancia_elenco DESC
LIMIT 10;
""",
        "5. Principais Talentos por Nacionalidade (Top 5 Concatenados)": """
-- Agrupa atletas por país e concatena os 5 maiores destaques de cada nação
WITH RankedTopPlayers AS (
    SELECT 
        p.nationality AS pais,
        p.name AS jogador,
        p.rating_global,
        ROW_NUMBER() OVER (
            PARTITION BY p.nationality 
            ORDER BY p.rating_global DESC, p.name ASC
        ) AS rk
    FROM players p
    WHERE p.rating_global >= 75
),
CountryTotals AS (
    SELECT 
        p.nationality AS pais,
        COUNT(p.id) AS total_atletas_top,
        ROUND(AVG(p.rating_global), 2) AS rating_medio_top
    FROM players p
    WHERE p.rating_global >= 75
    GROUP BY p.nationality
)
SELECT 
    ct.pais,
    ct.total_atletas_top,
    ct.rating_medio_top,
    GROUP_CONCAT(rtp.jogador, ', ') AS top_5_destaques
FROM CountryTotals ct
JOIN RankedTopPlayers rtp ON ct.pais = rtp.pais
WHERE rtp.rk <= 5
GROUP BY ct.pais, ct.total_atletas_top, ct.rating_medio_top
HAVING ct.total_atletas_top >= 2
ORDER BY ct.total_atletas_top DESC, ct.rating_medio_top DESC;
"""
    }
    
    selected_query_title = st.selectbox("📌 Selecione uma Consulta SQL da Suíte de testes:", list(queries.keys()))
    current_query = queries[selected_query_title]
    
    st.subheader("💻 Código SQL Nativo")
    st.code(current_query, language="sql")
    
    if st.button("▶️ Executar Consulta SQL", type="primary"):
        try:
            df_sql_res = pd.read_sql_query(current_query, conn)
            
            st.success(f"✅ Consulta executada com sucesso! Retornou **{len(df_sql_res)}** linhas.")
            st.subheader("📈 Resultado da Análise Relacional")
            st.dataframe(df_sql_res, use_container_width=True, hide_index=True)
            
            if "faixa_etaria" in df_sql_res.columns and "rating_medio" in df_sql_res.columns:
                fig = px.bar(
                    df_sql_res, 
                    x="faixa_etaria", 
                    y="rating_medio", 
                    color="faixa_etaria",
                    title="Rating Médio por Faixa Etária (Maturidade Física)",
                    text_auto=True
                )
                st.plotly_chart(fig, use_container_width=True)
                
            elif "diferencial_forca" in df_sql_res.columns and "clube" in df_sql_res.columns:
                fig = px.bar(
                    df_sql_res, 
                    x="diferencial_forca", 
                    y="clube", 
                    orientation="h",
                    color="diferencial_forca",
                    title="Diferencial de Força do Elenco em Relação à Média da Liga",
                    color_continuous_scale="Blues"
                )
                st.plotly_chart(fig, use_container_width=True)
                
            elif "variancia_elenco" in df_sql_res.columns and "clube" in df_sql_res.columns:
                fig = px.bar(
                    df_sql_res,
                    x="clube",
                    y="variancia_elenco",
                    color="variancia_elenco",
                    title="Dispersão e Variância Interna do Elenco",
                    color_continuous_scale="Oranges"
                )
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"❌ Erro na execução do SQL: {e}")

st.divider()
st.caption("Futebol Analytics Project • Desenvolvido com Streamlit, SQLite & Python")