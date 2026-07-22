import sqlite3
import pandas as pd

conn = sqlite3.connect("futebol.db")
cursor = conn.cursor()

# Inspect column names in teams and players tables to guarantee compatibility
teams_cols = [col[1] for col in cursor.execute("PRAGMA table_info(teams)").fetchall()]
players_cols = [col[1] for col in cursor.execute("PRAGMA table_info(players)").fetchall()]

# Identify the league column dynamically
if "league" in teams_cols:
    league_col = "t.league"
elif "league_name" in teams_cols:
    league_col = "t.league_name"
elif "competition" in teams_cols:
    league_col = "t.competition"
elif "league" in players_cols:
    league_col = "p.league"
elif "league_name" in players_cols:
    league_col = "p.league_name"
else:
    league_col = "'Liga Principal'"

print(f"🔌 Conectado ao futebol.db | Coluna de Liga identificada: {league_col}")

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
    "2. Comparativo do Elenco vs Média da Liga": f"""
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
        HAVING num_jogadores >= 11
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

for title, query in queries.items():
    print("\n" + "="*60)
    print(f"▶️ {title}")
    print("="*60)
    try:
        df = pd.read_sql_query(query, conn)
        print(df.to_string(index=False))
        print(f"\n✅ Linhas retornadas: {len(df)}")
    except Exception as e:
        print(f"❌ Erro ao executar consulta: {e}")

conn.close()