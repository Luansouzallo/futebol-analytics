import os
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id TEXT PRIMARY KEY,
            name TEXT,
            code TEXT,
            area TEXT
        )
    """)

    # Tabela de Times
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            tla TEXT,
            venue TEXT,
            competition_code TEXT
        )
    """)

    # Tabela de Jogadores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            position TEXT,
            date_of_birth TEXT,
            nationality TEXT,
            team_id INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")

def populate_league(competition_code="PL"):
    """Busca times e jogadores de um campeonato na API e salva no SQLite."""
    init_db()
    
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/teams"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"❌ Erro ao buscar dados da liga {competition_code}: {response.status_code}")
        return

    data = response.json()
    teams = data.get("teams", [])
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"🔄 Processando {len(teams)} times para o campeonato '{competition_code}'...")

    for team in teams:
        team_id = team.get("id")
        team_name = team.get("name")
        tla = team.get("tla")
        venue = team.get("venue")

        # Insere ou atualiza o Time
        cursor.execute("""
            INSERT INTO teams (id, name, tla, venue, competition_code)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                tla=excluded.tla,
                venue=excluded.venue,
                competition_code=excluded.competition_code
        """, (team_id, team_name, tla, venue, competition_code))

        # Pega o elenco (squad) do time
        squad = team.get("squad", [])
        for player in squad:
            player_id = player.get("id")
            player_name = player.get("name")
            position = player.get("position")
            date_of_birth = player.get("dateOfBirth")
            nationality = player.get("nationality")

            # Insere ou atualiza o Jogador
            cursor.execute("""
                INSERT INTO players (id, name, position, date_of_birth, nationality, team_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    position=excluded.position,
                    date_of_birth=excluded.date_of_birth,
                    nationality=excluded.nationality,
                    team_id=excluded.team_id
            """, (player_id, player_name, position, date_of_birth, nationality, team_id))

    conn.commit()
    conn.close()
    print(f"✨ População concluída com sucesso para a liga {competition_code}!")

def check_database():
    """Função rápida para conferir quantos registros foram salvos."""
    conn = sqlite3.connect(DB_NAME)
    
    df_teams = pd.read_sql_query("SELECT COUNT(*) as total_times FROM teams", conn)
    df_players = pd.read_sql_query("SELECT COUNT(*) as total_jogadores FROM players", conn)
    df_sample = pd.read_sql_query("""
        SELECT p.name AS jogador, p.position AS posicao, t.name AS time
        FROM players p
        JOIN teams t ON p.team_id = t.id
        LIMIT 10
    """, conn)
    
    conn.close()
    
    print("\n📊 Resumo do Banco de Dados:")
    print(df_teams)
    print(df_players)
    print("\n🔍 Amostra dos jogadores salvos:")
    print(df_sample)

# Executa a população da Premier League e verifica o banco
populate_league("PL")
check_database()