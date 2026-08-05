import os
import random
import sqlite3
import requests
import pandas as pd
from dotenv import load_dotenv

# Carrega a API Key
load_dotenv()
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
HEADERS = {"X-Auth-Token": API_KEY}
DB_NAME = "futebol.db"


def init_db():
    """Cria as tabelas no banco de dados SQLite caso ainda não existam."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabela de Ligas/Campeonatos
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY,
            name TEXT,
            code TEXT UNIQUE,
            area TEXT
        )
    """
    )

    # Tabela de Times
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            tla TEXT,
            venue TEXT,
            competition_code TEXT,
            FOREIGN KEY (competition_code) REFERENCES competitions (code)
        )
    """
    )

    # Tabela de Jogadores (com a coluna rating_global adicionada)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            position TEXT,
            date_of_birth TEXT,
            nationality TEXT,
            rating_global REAL,
            team_id INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        )
    """
    )

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")


def populate_league(competition_code="PL"):
    """Busca campeonatos, times e jogadores na API e salva no SQLite."""
    init_db()

    url = f"https://api.football-data.org/v4/competitions/{competition_code}/teams"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(
            f"❌ Erro ao buscar dados da liga {competition_code}: {response.status_code}"
        )
        return

    data = response.json()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Popula a tabela de Competições
    comp = data.get("competition", {})
    if comp:
        cursor.execute(
            """
            INSERT INTO competitions (id, name, code, area)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                code=excluded.code,
                area=excluded.area
        """,
            (
                comp.get("id"),
                comp.get("name"),
                comp.get("code"),
                comp.get("area", {}).get("name"),
            ),
        )

    # 2. Popula Times e Jogadores
    teams = data.get("teams", [])
    print(
        f"🔄 Processando {len(teams)} times para o campeonato '{competition_code}'..."
    )

    for team in teams:
        team_id = team.get("id")
        team_name = team.get("name")
        tla = team.get("tla")
        venue = team.get("venue")

        cursor.execute(
            """
            INSERT INTO teams (id, name, tla, venue, competition_code)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                tla=excluded.tla,
                venue=excluded.venue,
                competition_code=excluded.competition_code
        """,
            (team_id, team_name, tla, venue, competition_code),
        )

        squad = team.get("squad", [])
        for player in squad:
            player_id = player.get("id")
            player_name = player.get("name")
            position = player.get("position")
            date_of_birth = player.get("dateOfBirth")
            nationality = player.get("nationality")

            # Gera um rating fictício entre 60.0 e 95.0 para testes na interface
            rating_global = round(random.uniform(60.0, 95.0), 1)

            cursor.execute(
                """
                INSERT INTO players (id, name, position, date_of_birth, nationality, rating_global, team_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    position=excluded.position,
                    date_of_birth=excluded.date_of_birth,
                    nationality=excluded.nationality,
                    team_id=excluded.team_id
            """,
                (
                    player_id,
                    player_name,
                    position,
                    date_of_birth,
                    nationality,
                    rating_global,
                    team_id,
                ),
            )

    conn.commit()
    conn.close()
    print(f"✨ População concluída com sucesso para a liga {competition_code}!")


def check_database():
    """Função para conferir a integridade do banco e simular a query do ranking."""
    conn = sqlite3.connect(DB_NAME)

    df_teams = pd.read_sql_query(
        "SELECT COUNT(*) as total_times FROM teams", conn
    )
    df_players = pd.read_sql_query(
        "SELECT COUNT(*) as total_jogadores FROM players", conn
    )

    # Query corrigida com os JOINs para a Streamlit
    query_ranking = """
        SELECT 
            p.name AS Jogador, 
            t.name AS Clube, 
            c.name AS Liga, 
            p.position AS Posição, 
            p.nationality AS Nacionalidade, 
            p.rating_global AS 'Rating Global' 
        FROM players p 
        JOIN teams t ON p.team_id = t.id 
        LEFT JOIN competitions c ON t.competition_code = c.code
        ORDER BY p.rating_global DESC
        LIMIT 10;
    """

    df_ranking = pd.read_sql_query(query_ranking, conn)
    conn.close()

    print("\n📊 Resumo do Banco de Dados:")
    print(df_teams)
    print(df_players)
    print("\n🏆 Top 10 Ranking Global (Resultado da Query Corrigida):")
    print(df_ranking)


if __name__ == "__main__":
    populate_league("PL")
    check_database()