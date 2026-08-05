import sqlite3
import pandas as pd
import numpy as np
import math
from datetime import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

try:
    from lifecycle_tracker import load_config, calculate_db_hash, log_simulation_run
except ImportError:
    def load_config(path="config.yaml"):
        return {
            "version": "1.2.0",
            "simulation_engine": {"poisson": {"home_advantage": 2.5, "base_lambda": 1.35, "sensitivity_factor": 0.04, "min_lambda": 0.2, "max_goals_matrix": 6}},
            "mlops": {"mlflow": {"model_stage": "Production"}}
        }
    def calculate_db_hash(path="futebol.db"):
        return "demo-hash", "⚠️ Módulo Tracker ausente"
    def log_simulation_run(*args, **kwargs):
        return "fallback-id"

try:
    from drift_detector import check_data_drift, check_concept_drift, generate_synthetic_reference_baseline
except ImportError:
    def check_data_drift(ref, cur, alpha=0.05, feature_name="rating"):
        return {"drift_detected": False, "status": "✅ Estável (Fallback)", "ks_statistic": 0.0, "p_value": 1.0, "ref_mean": 85.0, "cur_mean": 85.0, "ref_std": 3.0, "cur_std": 3.0, "delta_mean": 0.0}
    def check_concept_drift(obs, exp=0.45, thresh=0.12):
        return {"drift_detected": False, "status": "✅ Estável (Fallback)", "recommendation": "Sem alterações."}
    def generate_synthetic_reference_baseline(cur, shift_mean=0.0, noise_std=1.0):
        return np.random.normal(85.0, 3.0, len(cur))

cfg = load_config("config.yaml")
app_cfg = cfg.get("app", {})
poisson_cfg = cfg.get("simulation_engine", {}).get("poisson", {})
rating_cfg = cfg.get("rating_engine", {})
mlops_cfg = cfg.get("mlops", {})

st.set_page_config(
    page_title=app_cfg.get("title", "Futebol Analytics & Match Simulator"),
    page_icon=app_cfg.get("page_icon", "⚽"),
    layout=app_cfg.get("layout", "wide"),
    initial_sidebar_state="expanded"
)

@st.cache_resource
def get_db_connection():
    """Conecta ao banco de dados SQLite local ou cria banco em memória de fallback."""
    db_path = cfg.get("database", {}).get("db_path", "futebol.db")
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        if "players" in tables and "teams" in tables:
            return conn, False
    except Exception:
        pass
    
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

def calculate_xai_components(final_rating: float, date_of_birth_str: str, league_name: str, config_dict: dict):
    age_adjustments = config_dict.get("rating_engine", {}).get("age_adjustments", {})
    league_multipliers = config_dict.get("rating_engine", {}).get("league_multipliers", {})

    age_factor = 0.0
    if date_of_birth_str:
        try:
            birth_year = int(date_of_birth_str.split("-")[0])
            current_year = datetime.now().year
            age = current_year - birth_year
            
            if 24 <= age <= 29:
                age_factor = age_adjustments.get("peak_performance", {}).get("adjustment", 3.5)
            elif 21 <= age <= 23:
                age_factor = age_adjustments.get("development", {}).get("adjustment", 1.5)
            elif age < 21:
                age_factor = age_adjustments.get("prospect", {}).get("adjustment", 0.5)
            elif 30 <= age <= 34:
                age_factor = age_adjustments.get("decline", {}).get("adjustment", -1.0)
            else:
                age_factor = age_adjustments.get("veteran", {}).get("adjustment", -2.5)
        except Exception:
            age_factor = 0.0

    league_factor = league_multipliers.get(str(league_name), league_multipliers.get("Default", 2.0))
    base_rating = final_rating - age_factor - league_factor
    return round(base_rating, 2), round(age_factor, 2), round(league_factor, 2)

conn, is_sample = get_db_connection()
league_col = get_league_column(conn)

# Busca ratings atuais do banco para monitoramento de drift
df_ratings_db = pd.read_sql_query("SELECT rating_global FROM players WHERE rating_global IS NOT NULL", conn)
current_ratings_arr = df_ratings_db["rating_global"].values if not df_ratings_db.empty else np.array([85.0])

# Execução do Teste de Data Drift
ref_baseline_arr = generate_synthetic_reference_baseline(current_ratings_arr, shift_mean=0.0, noise_std=1.0)
drift_report = check_data_drift(ref_baseline_arr, current_ratings_arr, alpha=0.05, feature_name="rating_global")

# Sidebar de MLOps & Governança
with st.sidebar:
    st.header("🛡️ MLOps & Governança")
    st.markdown("Monitoramento do Ciclo de Vida e Reprodutibilidade")
    
    db_file_path = cfg.get("database", {}).get("db_path", "futebol.db")
    db_hash, db_status = calculate_db_hash(db_file_path)
    
    st.info(f"**Status DB:** {db_status}")
    st.caption(f"**MD5 Hash:** `{db_hash[:16]}...`")
    st.divider()
    
    st.markdown("### 📉 Drift Status (KS-Test)")
    if drift_report["drift_detected"]:
        st.error(f"{drift_report['status']}")
    else:
        st.success(f"{drift_report['status']}")
        
    st.caption(f"**KS Stat:** `{drift_report['ks_statistic']}` | **p-value:** `{drift_report['p_value']}`")
    st.divider()
    
    st.markdown(f"📌 **Versão App/Config:** `v{cfg.get('version', '1.2.0')}`")
    st.markdown(f"📌 **Ambiente:** `{cfg.get('environment', 'production').upper()}`")
    st.markdown(f"📌 **Estágio do Modelo:** `{mlops_cfg.get('mlflow', {}).get('model_stage', 'Production')}`")
    st.markdown(f"🎲 **Poisson Seed:** `{poisson_cfg.get('random_seed', 42)}`")

st.title("⚽ Futebol Analytics & Match Simulator")
st.caption("Plataforma Integrada de Inteligência Esportiva, MLOps e Análise Relacional SQL")

if is_sample:
    st.warning("⚠️ Exibindo modo de demonstração com dados em memória. Conecte seu arquivo `futebol.db` para carregar o banco completo.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎮 Simulador de Partidas", 
    "🏆 Ranking Global", 
    "📋 Elencos & Explicabilidade (XAI)", 
    "📊 SQL Analytics Lab",
    "📉 Data & Concept Drift"
])

with tab1:
    st.header("🎮 Simulador Probabilístico de Partidas")
    st.markdown("Previsão baseada no modelo estatístico da **Distribuição de Poisson** e diferencial de rating dos elencos.")
    
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
        
        home_adv = poisson_cfg.get("home_advantage", 2.5)
        
        with col_home:
            st.subheader("🏠 Time Mandante")
            home_team = st.selectbox("Escolha o Mandante", team_list, index=0, key="home_select")
            home_rating = df_teams[df_teams["clube"] == home_team]["rating_medio"].values[0]
            st.metric("Rating Médio (Mandante)", home_rating, delta=f"+{home_adv:.1f} (Fator Casa)")
            
        with col_vs:
            st.markdown("<h2 style='text-align: center; margin-top: 30px;'>VS</h2>", unsafe_allow_html=True)
            
        with col_away:
            st.subheader("✈️ Time Visitante")
            away_default_idx = 1 if len(team_list) > 1 else 0
            away_team = st.selectbox("Escolha o Visitante", team_list, index=away_default_idx, key="away_select")
            away_rating = df_teams[df_teams["clube"] == away_team]["rating_medio"].values[0]
            st.metric("Rating Médio (Visitante)", away_rating)
            
        st.divider()
        
        if st.button("▶️ Simular Partida & Logar MLOps", type="primary", use_container_width=True):
            base_lambda = poisson_cfg.get("base_lambda", 1.35)
            sensitivity = poisson_cfg.get("sensitivity_factor", 0.04)
            min_lambda = poisson_cfg.get("min_lambda", 0.2)
            max_g = poisson_cfg.get("max_goals_matrix", 6)
            
            home_effective = home_rating + home_adv
            diff = home_effective - away_rating
            
            lambda_home = max(min_lambda, base_lambda + (diff * sensitivity))
            lambda_away = max(min_lambda, base_lambda - (diff * sensitivity))
            
            seed = poisson_cfg.get("random_seed")
            if seed is not None:
                np.random.seed(seed)
                
            home_goals = np.random.poisson(lambda_home)
            away_goals = np.random.poisson(lambda_away)
            
            st.subheader("🏆 Placar Simulado")
            col_res1, col_res2 = st.columns(2)
            col_res1.metric(home_team, f"{home_goals} Gol(s)", help=f"λ = {lambda_home:.2f}")
            col_res2.metric(away_team, f"{away_goals} Gol(s)", help=f"λ = {lambda_away:.2f}")
            
            matrix = np.zeros((max_g, max_g))
            for i in range(max_g):
                for j in range(max_g):
                    matrix[i, j] = (np.power(lambda_home, i) * np.exp(-lambda_home) / math.factorial(i)) * \
                                   (np.power(lambda_away, j) * np.exp(-lambda_away) / math.factorial(j))
            
            prob_home = float(np.sum(np.tril(matrix, -1)) * 100)
            prob_draw = float(np.sum(np.diag(matrix)) * 100)
            prob_away = float(np.sum(np.triu(matrix, 1)) * 100)
            
            st.subheader("📊 Probabilidade dos Resultados")
            col_p1, col_p2, col_p3 = st.columns(3)
            col_p1.metric(f"Vitória - {home_team}", f"{prob_home:.1f}%")
            col_p2.metric("Empate", f"{prob_draw:.1f}%")
            col_p3.metric(f"Vitória - {away_team}", f"{prob_away:.1f}%")
            
            run_id = log_simulation_run(
                home_team=home_team,
                away_team=away_team,
                home_rating=home_rating,
                away_rating=away_rating,
                lambda_home=lambda_home,
                lambda_away=lambda_away,
                prob_home=prob_home,
                prob_draw=prob_draw,
                prob_away=prob_away,
                config=cfg
            )
            
            st.toast(f"🚀 Simulação registrada no Lifecycle Tracker! Run ID: `{run_id}`")

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
    st.header("📋 Análise Detalhada de Elencos & Explicabilidade (XAI)")
    
    teams_query = pd.read_sql_query("SELECT id, name FROM teams ORDER BY name", conn)
    selected_team_name = st.selectbox("Selecione o Clube para Análise:", teams_query["name"].tolist())
    
    df_squad = pd.read_sql_query(f"""
        SELECT 
            p.name AS Jogador,
            p.position AS Posição,
            p.nationality AS Nacionalidade,
            p.date_of_birth AS "Data Nascimento",
            {league_col} AS Liga,
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
    
    st.dataframe(df_squad[["Jogador", "Posição", "Nacionalidade", "Data Nascimento", "Rating Global"]], use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.subheader("🧠 Módulo XAI: Explicabilidade do Rating de Atletas")
    st.markdown("Decomposição transparente alimentada pelas regras definidas no arquivo `config.yaml`.")
    
    if not df_squad.empty:
        selected_player = st.selectbox("Selecione um jogador para analisar:", df_squad["Jogador"].tolist(), key="xai_player_select")
        player_row = df_squad[df_squad["Jogador"] == selected_player].iloc[0]
        
        final_rating = player_row["Rating Global"]
        dob = player_row["Data Nascimento"]
        league = player_row["Liga"]
        
        base_r, age_adj, league_adj = calculate_xai_components(final_rating, dob, league, cfg)
        
        fig_xai = go.Figure(go.Waterfall(
            name="XAI Rating Breakdown",
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["Rating Base", "Ajuste Etário", "Peso da Liga", "Rating Final"],
            textposition="outside",
            text=[f"{base_r:.1f}", f"{age_adj:+.1f}", f"{league_adj:+.1f}", f"{final_rating:.1f}"],
            y=[base_r, age_adj, league_adj, 0],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "#EF553B"}},
            increasing={"marker": {"color": "#00CC96"}},
            totals={"marker": {"color": "#636EFA"}}
        ))
        
        fig_xai.update_layout(
            title=f"Decomposição de Performance: {selected_player} ({player_row['Posição']})",
            yaxis_title="Pontos de Rating",
            showlegend=False,
            height=450
        )
        
        st.plotly_chart(fig_xai, use_container_width=True)

with tab4:
    st.header("📊 SQL Analytics Lab")
    st.markdown("Execute consultas SQL avançadas (*Window Functions*, *CTEs*, *CASE WHEN*, *Variância*) diretamente no banco relacional.")
    
    queries = {
        "1. Top 3 Atletas por Posição em Cada Liga (Window Functions)": f"""
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
    
    selected_query_title = st.selectbox("📌 Selecione uma Consulta SQL da Suíte:", list(queries.keys()))
    current_query = queries[selected_query_title]
    
    st.subheader("💻 Código SQL Nativo")
    st.code(current_query, language="sql")
    
    if st.button("▶️ Executar Consulta SQL", type="primary"):
        try:
            df_sql_res = pd.read_sql_query(current_query, conn)
            st.success(f"✅ Consulta executada com sucesso! Retornou **{len(df_sql_res)}** linhas.")
            st.dataframe(df_sql_res, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"❌ Erro na execução do SQL: {e}")

with tab5:
    st.header("📉 Painel de Monitoramento: Data Drift & Concept Drift")
    st.markdown("Detecção de alterações estatísticas nas variáveis de entrada (*Data Drift*) e perda de validade das premissas do modelo (*Concept Drift*).")
    
    st.subheader("1. 📉 Data Drift: Rating Global de Atletas (Kolmogorov-Smirnov Test)")
    
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric("Status Data Drift", drift_report["status"].split(" ")[1] if " " in drift_report["status"] else drift_report["status"])
    col_d2.metric("Estatística KS ($D$)", f"{drift_report['ks_statistic']:.4f}")
    col_d3.metric("p-Valor ($p$)", f"{drift_report['p_value']:.4f}", help="Drift se p < alpha (0.05)")
    col_d4.metric("Δ Média de Ratings", f"{drift_report['delta_mean']:+.2f} pts")
    
    st.markdown("#### 🧪 Simulação Interativa de Ingestão de Ligas (Data Drift Stress Test)")
    shift_val = st.slider("Simular deslocamento de média na nova ingestão de dados (Shift):", -10.0, 10.0, 0.0, step=0.5)
    noise_val = st.slider("Simular alteração no desvio padrão (Variância):", 0.5, 3.0, 1.0, step=0.1)
    
    sim_cur_ratings = current_ratings_arr + shift_val
    sim_ref_ratings = generate_synthetic_reference_baseline(sim_cur_ratings, shift_mean=0.0, noise_std=noise_val)
    
    sim_drift_res = check_data_drift(sim_ref_ratings, sim_cur_ratings, alpha=0.05)
    
    if sim_drift_res["drift_detected"]:
        st.error(f"🚨 **ALERTA DE DRIFT DETECTADO!** {sim_drift_res['status']} — A nova distribuição diverge da base de referência.")
    else:
        st.success(f"✅ **DISTRIBUIÇÃO ESTÁVEL:** {sim_drift_res['status']} — As distribuições mantêm equivalência estatística.")
        
    fig_drift = go.Figure()
    fig_drift.add_trace(go.Histogram(x=sim_ref_ratings, name="Histórico (Referência)", opacity=0.6, marker_color="#1F77B4"))
    fig_drift.add_trace(go.Histogram(x=sim_cur_ratings, name="Ingestão Atual (Simulada)", opacity=0.6, marker_color="#FF7F0E"))
    fig_drift.update_layout(
        title="Comparação da Distribuição de Ratings (KS-Test Overlay)",
        barmode="overlay",
        xaxis_title="Rating Global",
        yaxis_title="Contagem de Atletas",
        height=400
    )
    st.plotly_chart(fig_drift, use_container_width=True)
    
    st.divider()
    
    st.subheader("2. 🔄 Concept Drift: Validação da Premissa do Mando de Campo")
    st.markdown("Mede se a taxa observada de vitórias dos mandantes nas partidas recentes ainda suporta a premissa de $+2.5$ de rating fixado no motor Poisson.")
    
    obs_win_rate = st.slider("Taxa de vitória recente do mandante observada na liga (%):", 10.0, 70.0, 44.0, step=1.0) / 100.0
    exp_win_rate = poisson_cfg.get("expected_home_win_rate", 0.45)
    
    concept_res = check_concept_drift(observed_home_win_rate=obs_win_rate, expected_home_win_rate=exp_win_rate)
    
    col_c1, col_c2, col_c3 = st.columns(3)
    col_c1.metric("Taxa Observada", f"{obs_win_rate*100:.1f}%")
    col_c2.metric("Taxa Teórica Esperada", f"{exp_win_rate*100:.1f}%")
    col_c3.metric("Diferença Absoluta", f"{concept_res['difference']*100:.1f}%")
    
    if concept_res["drift_detected"]:
        st.warning(f"{concept_res['status']}")
        st.info(f"💡 **Recomendação MLOps:** {concept_res['recommendation']}")
    else:
        st.success(f"{concept_res['status']}")

st.divider()
st.caption(f"Futebol Analytics Project • Config v{cfg.get('version', '1.2.0')} • Desenvolvido com Streamlit, SQLite, MLflow & Python")