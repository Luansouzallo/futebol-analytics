import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Union, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DriftDetector")

try:
    from scipy.stats import ks_2samp, ttest_ind
    HAS_SCIPY = True
    logger.info("scipy detectado. Testes de Kolmogorov-Smirnov e T-Test ativados.")
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy não instalado. Drift detector operando em modo fallback por desvio estático.")


def check_data_drift(
    reference_data: Union[np.ndarray, pd.Series, list],
    current_data: Union[np.ndarray, pd.Series, list],
    alpha: float = 0.05,
    feature_name: str = "rating_global"
) -> Dict[str, Any]:
    """
    Executa o teste estatístico de Kolmogorov-Smirnov (KS-Test) para comparar a distribuição
    dos dados de referência (históricos) contra os dados atuais ingeridos.

    Parâmetros:
    -----------
    reference_data : array-like
        Valores de referência histórica (ex: ratings prévios da liga).
    current_data : array-like
        Valores da rodada/ingestão atual.
    alpha : float
        Nível de significância (p-value threshold, padrão 0.05).
    feature_name : str
        Nome da variável analisada.

    Retorna:
    --------
    dict com status do drift, estatística KS, p-valor e métricas descritivas comparativas.
    """
    ref_clean = np.asarray(reference_data, dtype=float)
    ref_clean = ref_clean[~np.isnan(ref_clean)]

    cur_clean = np.asarray(current_data, dtype=float)
    cur_clean = cur_clean[~np.isnan(cur_clean)]

    if len(ref_clean) == 0 or len(cur_clean) == 0:
        return {
            "feature": feature_name,
            "drift_detected": False,
            "status": "⚠️ Dados Insuficientes",
            "reason": "Dados de entrada vazios ou ausentes.",
            "ks_statistic": 0.0,
            "p_value": 1.0,
            "ref_mean": 0.0,
            "cur_mean": 0.0,
            "ref_std": 0.0,
            "cur_std": 0.0
        }

    ref_mean, ref_std = float(np.mean(ref_clean)), float(np.std(ref_clean))
    cur_mean, cur_std = float(np.mean(cur_clean)), float(np.std(cur_clean))
    delta_mean = cur_mean - ref_mean

    if HAS_SCIPY and len(ref_clean) >= 5 and len(cur_clean) >= 5:
        try:
            stat, p_value = ks_2samp(ref_clean, cur_clean)
            stat = round(float(stat), 4)
            p_value = round(float(p_value), 4)
            drift_detected = p_value < alpha
            status_msg = "🚨 Data Drift Detectado!" if drift_detected else "✅ Distribuição Estável"
        except Exception as e:
            logger.error(f"Falha ao executar teste KS: {e}")
            drift_detected = abs(delta_mean) > (1.5 * ref_std) if ref_std > 0 else False
            stat, p_value = 0.0, 1.0
            status_msg = "⚠️ Desvio na Média (Fallback)" if drift_detected else "✅ Estável (Fallback)"
    else:
        # Fallback estatístico baseado no desvio padrão relativo da média
        drift_threshold = 1.5 * ref_std if ref_std > 0 else 5.0
        drift_detected = abs(delta_mean) > drift_threshold
        stat, p_value = 0.0, 1.0
        status_msg = "🚨 Data Drift Detectado (Simulado)" if drift_detected else "✅ Distribuição Estável (Simulado)"

    return {
        "feature": feature_name,
        "drift_detected": drift_detected,
        "status": status_msg,
        "alpha": alpha,
        "ks_statistic": stat,
        "p_value": p_value,
        "ref_mean": round(ref_mean, 2),
        "cur_mean": round(cur_mean, 2),
        "ref_std": round(ref_std, 2),
        "cur_std": round(cur_std, 2),
        "delta_mean": round(delta_mean, 2),
        "sample_size_ref": len(ref_clean),
        "sample_size_cur": len(cur_clean)
    }


def check_concept_drift(
    observed_home_win_rate: float,
    expected_home_win_rate: float = 0.45,
    threshold_margin: float = 0.12
) -> Dict[str, Any]:
    """
    Avalia a ocorrência de Concept Drift comparando a relação estatística observada nos resultados
    reais (ex: taxa de vitória do mandante recente) com a premissa teórica do modelo (mando de casa = +2.5).

    Parâmetros:
    -----------
    observed_home_win_rate : float
        Taxa real de vitória dos mandantes nas últimas partidas (0.0 a 1.0).
    expected_home_win_rate : float
        Taxa esperada teórica segundo a parametrização do modelo (padrão 0.45 ou 45%).
    threshold_margin : float
        Margem de tolerância aceitável antes de indicar perda de acurácia da premissa.
    """
    diff = abs(observed_home_win_rate - expected_home_win_rate)
    drift_detected = diff > threshold_margin

    if drift_detected:
        if observed_home_win_rate < expected_home_win_rate:
            recommendation = "Reduzir parâmetro home_advantage (ex: de 2.5 para 1.0) no config.yaml"
        else:
            recommendation = "Aumentar parâmetro home_advantage no config.yaml"
        status_msg = "🚨 Concept Drift Detectado! Premissa de Mando de Campo desatualizada."
    else:
        recommendation = "Manter parâmetro home_advantage atual (2.5)."
        status_msg = "✅ Concept Drift Não Detectado. Premissa válida."

    return {
        "drift_detected": drift_detected,
        "status": status_msg,
        "observed_win_rate": round(observed_home_win_rate, 3),
        "expected_win_rate": round(expected_home_win_rate, 3),
        "difference": round(diff, 3),
        "threshold": threshold_margin,
        "recommendation": recommendation
    }


def generate_synthetic_reference_baseline(
    current_data: Union[np.ndarray, pd.Series],
    shift_mean: float = 0.0,
    noise_std: float = 1.0
) -> np.ndarray:
    """
    Gera uma distribuição baseline sintética de referência histórica para fins de teste
    e simulação quando o histórico prévio de banco não estiver disponível.
    """
    cur_arr = np.asarray(current_data, dtype=float)
    cur_arr = cur_arr[~np.isnan(cur_arr)]
    if len(cur_arr) == 0:
        return np.array([75.0, 80.0, 85.0, 90.0])

    base_mean = np.mean(cur_arr) + shift_mean
    base_std = max(0.5, np.std(cur_arr) * noise_std)
    np.random.seed(42)
    return np.random.normal(loc=base_mean, scale=base_std, size=len(cur_arr))


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Testando Módulo Drift Detector Engine")
    print("=" * 60)

    # 1. Teste de Data Drift Sem Drift
    hist_ratings = np.random.normal(loc=85.0, scale=4.0, size=200)
    new_ratings_stable = np.random.normal(loc=85.1, scale=4.1, size=150)
    res_stable = check_data_drift(hist_ratings, new_ratings_stable)
    print("📌 Teste 1 (Distribuição Estável):", res_stable["status"])
    print(f"   KS Stat: {res_stable['ks_statistic']} | p-value: {res_stable['p_value']}")

    # 2. Teste de Data Drift Com Drift Significativo
    new_ratings_drifted = np.random.normal(loc=89.5, scale=5.0, size=150)
    res_drifted = check_data_drift(hist_ratings, new_ratings_drifted)
    print("\n📌 Teste 2 (Distribuição com Drift):", res_drifted["status"])
    print(f"   KS Stat: {res_drifted['ks_statistic']} | p-value: {res_drifted['p_value']}")

    # 3. Teste de Concept Drift
    concept_res = check_concept_drift(observed_home_win_rate=0.28, expected_home_win_rate=0.45)
    print("\n📌 Teste 3 (Concept Drift):", concept_res["status"])
    print(f"   Recomendação: {concept_res['recommendation']}")