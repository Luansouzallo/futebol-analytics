import os
import requests
import pandas as pd
from dotenv import load_dotenv

print("🚀 Iniciando o script...")

# Carrega a API Key do arquivo .env
load_dotenv()
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")

print(f"🔑 Chave carregada: {API_KEY[:5]}***" if API_KEY else "❌ Chave NÃO encontrada no .env!")

headers = {
    "X-Auth-Token": API_KEY
}

COMPETITION = "PL" 

def fetch_teams(competition_code):
    url = f"https://api.football-data.org/v4/competitions/{competition_code}/teams"
    print(f"📡 Fazendo requisição para: {url}")
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        teams = data.get("teams", [])
        
        teams_list = []
        for team in teams:
            teams_list.append({
                "id": team.get("id"),
                "name": team.get("name"),
                "tla": team.get("tla"),
                "venue": team.get("venue"),
                "website": team.get("website")
            })
        
        df = pd.DataFrame(teams_list)
        print(f"\n✅ Sucesso! {len(df)} times encontrados para {competition_code}:\n")
        print(df.head(10)) # Mostra os 10 primeiros
        return df
    else:
        print(f"\n❌ Erro na requisição: Código {response.status_code}")
        print(response.text)
        return None

# Executa a função diretamente
fetch_teams(COMPETITION)