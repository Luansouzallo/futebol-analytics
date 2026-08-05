import os
import hashlib
import logging
import yaml
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("LifecycleTracker")

try:
    import mlflow
    HAS_MLFLOW = True
    logger.info("MLflow detected. Experiment tracking is active.")
except ImportError:
    HAS_MLFLOW = False
    logger.warning("MLflow not installed. Experiment tracking will fallback to standard log output.")


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Carrega as configurações centralizadas do arquivo YAML.
    Retorna um dicionário com os parâmetros ou valores padrão de fallback.
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"Configuração carregada com sucesso a partir de '{config_path}'.")
                return config
        except Exception as e:
            logger.error(f"Erro ao ler '{config_path}': {e}. Utilizando configurações padrão.")
    else:
        logger.warning(f"Arquivo '{config_path}' não encontrado. Utilizando configurações padrão.")

    # Retorno de fallback caso o arquivo yaml não exista ou falhe
    return {
        "version": "1.2.0",
        "environment": "production",
        "simulation_engine": {
            "poisson": {
                "home_advantage": 2.5,
                "base_lambda": 1.35,
                "sensitivity_factor": 0.04,
                "min_lambda": 0.2,
                "random_seed": 42
            }
        },
        "mlops": {
            "mlflow": {
                "experiment_name": "futebol_analytics_simulations",
                "model_stage": "Production"
            }
        }
    }


def calculate_db_hash(db_path: str = "futebol.db") -> Tuple[str, str]:
    """
    Calcula o hash MD5 do arquivo SQLite para garantir reprodutibilidade e rastreabilidade da base.
    Retorna uma tupla: (hash_md5, status_str).
    """
    if not os.path.exists(db_path):
        return "in-memory-demo", "⚠️ Banco SQLite local ausente (Modo de Demonstração em Memória)"

    try:
        md5 = hashlib.md5()
        with open(db_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        digest = md5.hexdigest()
        logger.info(f"Hash MD5 do banco '{db_path}': {digest[:8]}...")
        return digest, f"✅ DB Synced (MD5: {digest[:8]}...)"
    except Exception as e:
        logger.error(f"Falha ao calcular Hash MD5 do banco '{db_path}': {e}")
        return "error-hash", f"❌ Erro ao ler banco ({e})"


def log_simulation_run(
    home_team: str,
    away_team: str,
    home_rating: float,
    away_rating: float,
    lambda_home: float,
    lambda_away: float,
    prob_home: float,
    prob_draw: float,
    prob_away: float,
    config: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Registra os parâmetros e métricas da simulação probabilística no MLflow.
    Caso o MLflow não esteja instalado, faz fallback transparente logando em console.
    """
    if config is None:
        config = load_config()

    poisson_cfg = config.get("simulation_engine", {}).get("poisson", {})
    mlflow_cfg = config.get("mlops", {}).get("mlflow", {})
    
    experiment_name = mlflow_cfg.get("experiment_name", "futebol_analytics_simulations")
    run_name = f"sim_{home_team}_vs_{away_team}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    params = {
        "home_team": home_team,
        "away_team": away_team,
        "home_base_rating": home_rating,
        "away_base_rating": away_rating,
        "home_advantage": poisson_cfg.get("home_advantage", 2.5),
        "base_lambda": poisson_cfg.get("base_lambda", 1.35),
        "sensitivity_factor": poisson_cfg.get("sensitivity_factor", 0.04),
        "model_stage": mlflow_cfg.get("model_stage", "Production"),
        "config_version": config.get("version", "1.2.0")
    }

    metrics = {
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
        "prob_home_win": round(prob_home, 2),
        "prob_draw": round(prob_draw, 2),
        "prob_away_win": round(prob_away, 2)
    }

    if HAS_MLFLOW:
        try:
            mlflow.set_experiment(experiment_name)
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.log_params(params)
                mlflow.log_metrics(metrics)
                logger.info(f"Simulação registrada no MLflow (Run ID: {run.info.run_id}).")
                return run.info.run_id
        except Exception as e:
            logger.error(f"Erro ao registrar simulação no MLflow: {e}")
            return None
    else:
        logger.info(f"[MLflow Fallback Mode] Run: {run_name}")
        logger.info(f"Parametros: {params}")
        logger.info(f"Metricas: {metrics}")
        return "fallback-local-log"


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Testando Módulo Lifecycle Tracker & MLOps")
    print("=" * 60)
    
    cfg = load_config()
    print(f"📌 Versão da Configuração: {cfg.get('version')}")
    print(f"📌 Estágio do Modelo: {cfg.get('mlops', {}).get('mlflow', {}).get('model_stage')}")
    
    db_hash, status_msg = calculate_db_hash("futebol.db")
    print(f"🔑 Hash MD5: {db_hash}")
    print(f"📋 Status: {status_msg}")
    
    run_id = log_simulation_run(
        home_team="Arsenal FC",
        away_team="Chelsea FC",
        home_rating=89.5,
        away_rating=85.2,
        lambda_home=1.52,
        lambda_away=0.98,
        prob_home=52.4,
        prob_draw=25.1,
        prob_away=22.5,
        config=cfg
    )
    print(f"🚀 Execution Run ID: {run_id}")