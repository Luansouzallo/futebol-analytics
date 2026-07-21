import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "futebol.db"

# Pesos de força dos campeonatos no cenário global
LEAGUE_WEIGHTS = {
    "PL": 1.00,   # Premier League
    "PD": 0.96,   # La Liga
    "SA": 0.94,   # Serie A
    "BL1": 0.93,  # Bundesliga
    "FL1": 0.90,  # Ligue 1
    "PPD": 0.83,  # Primeira Liga Portugal
    "CL": 0.98    # Champions League
}

def calculate_age(dob_str):
    """Calcula a idade a partir da data de nascimento (AAAA-MM-DD)."""
    # Trata valores nulos, vazios ou 'nan' do Pandas
    if pd.isna(dob_str) or not dob_str or str(dob_str).strip().lower() in ['none', 'nan', '']:
        return 26  # Idade média padrão se não informada
    
    try:
        birth_year = int(str(dob_str).split("-")[0])
        current_year = 2026
        return current_year - birth_year
    except (ValueError, IndexError):
        return 26

def generate_ratings():
    """Gera e salva as notas locais e globais dos jogadores no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Adiciona colunas de rating na tabela 'players' se ainda não existirem
    try:
        cursor.execute("ALTER TABLE players ADD COLUMN rating_league REAL")
        cursor.execute("ALTER TABLE players ADD COLUMN rating_global REAL")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Colunas já existem

    # Carrega jogadores e seus respectivos times
    query = """
        SELECT p.id, p.name, p.position, p.date_of_birth, t.name as team_name, t.competition_code
        FROM players p
        JOIN teams t ON p.team_id = t.id
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("❌ Nenhum jogador encontrado no banco!")
        conn.close()
        return

    # Semente determinística baseada no ID para gerar métricas consistentes
    np.random.seed(42)

    ratings_league = []
    ratings_global = []

    for _, row in df.iterrows():
        age = calculate_age(row["date_of_birth"])
        league_code = row["competition_code"]
        league_weight = LEAGUE_WEIGHTS.get(league_code, 0.80)

        # Base aleatória de qualidade individual (simulando scouts/estatísticas)
        base_skill = np.random.normal(loc=74, scale=6)

        # Bônus por idade no auge da carreira (entre 24 e 29 anos)
        if 24 <= age <= 29:
            age_bonus = 2.5
        elif age < 22:
            age_bonus = -1.0 # Jovem em desenvolvimento
        else:
            age_bonus = 0.0

        # Cálculo da Nota no Campeonato (0 a 100)
        local_rating = round(min(max(base_skill + age_bonus, 55.0), 99.0), 1)

        # Cálculo da Nota Global ajustada pelo nível da liga
        global_rating = round(min(max(local_rating * league_weight, 50.0), 99.0), 1)

        ratings_league.append(local_rating)
        ratings_global.append(global_rating)

    df["rating_league"] = ratings_league
    df["rating_global"] = ratings_global

    # Atualiza as notas no banco de dados SQLite
    for _, row in df.iterrows():
        cursor.execute("""
            UPDATE players 
            SET rating_league = ?, rating_global = ?
            WHERE id = ?
        """, (row["rating_league"], row["rating_global"], row["id"]))

    conn.commit()
    conn.close()
    print("✅ Ratings calculados e salvos no banco com sucesso!")

def show_top_players(limit=10):
    """Exibe os melhores jogadores cadastrados no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    query = f"""
        SELECT p.name AS Jogador, p.position AS Posição, t.name AS Time, 
               p.rating_league AS "Nota Liga", p.rating_global AS "Nota Global"
        FROM players p
        JOIN teams t ON p.team_id = t.id
        ORDER BY p.rating_global DESC
        LIMIT {limit}
    """
    df_top = pd.read_sql_query(query, conn)
    conn.close()

    print(f"\n🏆 Top {limit} Jogadores (Ranking Global):")
    print(df_top.to_string(index=False))

if __name__ == "__main__":
    generate_ratings()
    show_top_players(10)