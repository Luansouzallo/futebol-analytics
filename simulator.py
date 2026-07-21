import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "futebol.db"

def get_team_power(team_id):
    """Calcula a média de rating do time com base nos seus jogadores."""
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT AVG(rating_global) as overall_power
        FROM players
        WHERE team_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(team_id,))
    conn.close()
    
    power = df["overall_power"].iloc[0]
    return round(power, 2) if power else 70.0 # Valor default se não houver dados

def simulate_match(home_team_id, away_team_id):
    """Simula o resultado de uma partida entre dois times."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Busca nomes dos times
    cursor.execute("SELECT name FROM teams WHERE id = ?", (home_team_id,))
    home_name = cursor.fetchone()[0]

    cursor.execute("SELECT name FROM teams WHERE id = ?", (away_team_id,))
    away_name = cursor.fetchone()[0]

    conn.close()

    # Obtém a força dos elencos
    home_power = get_team_power(home_team_id)
    away_power = get_team_power(away_team_id)

    # Bônus de jogar em casa
    effective_home_power = home_power + 2.5 

    # Cálculo da média esperada de gols (Lambda da distribuição de Poisson)
    # A média normal de gols por time em uma partida é em torno de 1.3 a 1.5
    base_expected_goals = 1.35
    power_diff = (effective_home_power - away_power) / 10.0

    lambda_home = max(0.2, base_expected_goals + (power_diff * 0.4))
    lambda_away = max(0.2, base_expected_goals - (power_diff * 0.4))

    # Geração dos gols baseada em Poisson
    home_goals = np.random.poisson(lambda_home)
    away_goals = np.random.poisson(lambda_away)

    return {
        "home_team": home_name,
        "away_team": away_name,
        "home_power": home_power,
        "away_power": away_power,
        "home_goals": int(home_goals),
        "away_goals": int(away_goals),
    }

def print_match_result(sim_result):
    """Exibe o resultado da simulação de forma legível."""
    print("\n" + "="*45)
    print("⚽ SIMULAÇÃO DE PARTIDA ⚽")
    print("="*45)
    print(f"🏠 {sim_result['home_team']} (Força: {sim_result['home_power']})")
    print(f"✈️  {sim_result['away_team']} (Força: {sim_result['away_power']})")
    print("-"*45)
    print(f"   PLACAR FINAL: {sim_result['home_team']} {sim_result['home_goals']} x {sim_result['away_goals']} {sim_result['away_team']}")
    print("="*45 + "\n")

if __name__ == "__main__":
    # Teste de simulação: Arsenal (id: 57) vs Chelsea (id: 61)
    result = simulate_match(home_team_id=57, away_team_id=61)
    print_match_result(result)