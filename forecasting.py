"""
forecasting.py — Moteur de prévision S&OP
==========================================
VERSION 3.0 — Mai 2026

Méthodes disponibles :
  MA   — Moyenne Mobile (fenêtre optimisée automatiquement sur [2..12])
         Paramètres : AUCUN (α, β, γ ne s'appliquent pas)
  LES  — Lissage Exponentiel Simple
         Paramètre : α (alpha) uniquement — contrôle la réactivité au niveau
  HW   — Holt-Winters Additif (niveau + tendance + saisonnalité)
         Paramètres : α (niveau), β (tendance), γ (saisonnalité F(n,k))
         ⚠ Les facteurs saisonniers F(n,k) sont EXCLUSIFS à HW

Suppression de MBS/Holt :
  MBS et Holt-Double-Lissage ont été retirés car ils créaient une confusion
  avec MA (Moyenne Mobile). La gradation est désormais : MA → LES → HW.

Règle de sélection — MINIMISER l'erreur (MAPE) :
  La méthode avec le MAPE le plus FAIBLE est retenue.
  Règles métier S&OP en sus :
    R0 : n < 4  → MA uniquement
    R1 : n < 8  → MA + LES uniquement
    R2 : Saisonnalité détectée ET gain HW significatif (> SEUIL_MIN_GAIN=2 pts)
         → HW recommandé ; sinon LES pour la stabilité du plan
    R3 : CV > 60% → alerte série très volatile
    R4 : sinon → meilleur MAPE statistique

Définitions affichées dans l'interface :
  ERP      : Prévision issue du système ERP de l'entreprise (fichier importé).
             Sert de référence de comparaison pour mesurer le gain apporté
             par les méthodes Python (LES, HW).
  Int. bas / Int. haut : Intervalle de confiance à ~85% autour de la prévision.
             Calculé comme : Prévision ± 1.44 × RMSE × √horizon.
             Interprétation : dans ~85% des cas, la demande réelle sera dans cet intervalle.
  Anomalie : Valeur historique hors de l'intervalle [Moyenne ± 2×Écart-type].
             Une anomalie est un pic (valeur trop haute) ou un creux (valeur trop basse)
             qui s'écarte de plus de 2σ de la moyenne historique.
  Facteurs saisonniers F(n,k) : UNIQUEMENT dans HW.
             Représentent l'écart récurrent de chaque période (mois, semaine…)
             par rapport à la moyenne annuelle. Ex : F=1.25 → ce mois est 25%
             au-dessus de la moyenne. MA et LES n'ont pas de facteurs saisonniers.

Corrections v3.0 :
  - Suppression complète de MBS/Holt (confusion avec MA)
  - Paramètres affichés strictement par méthode (MA=aucun, LES=α, HW=α/β/γ)
  - Règle de sélection = MINIMISER MAPE (plus bas = meilleur)
  - Facteurs saisonniers réservés à HW uniquement
  - Corrections lookahead bias (ex-ante) maintenues de v2.0

Auteur  : AlBrain Consulting
Version : 3.0 — Mai 2026
"""

import numpy as np
import pandas as pd
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ForecastResult:
    method:           str
    alpha:            float = 0.0          # LES et HW uniquement
    beta:             float = 0.0          # HW uniquement
    gamma:            float = 0.0          # HW uniquement
    season_len:       int   = 0            # HW uniquement
    n_history:        int   = 0
    fitted:           np.ndarray = field(default_factory=lambda: np.array([]))
    forecast:         np.ndarray = field(default_factory=lambda: np.array([]))
    intervals_low:    np.ndarray = field(default_factory=lambda: np.array([]))
    intervals_high:   np.ndarray = field(default_factory=lambda: np.array([]))
    mae:              float = 0.0
    mape:             float = 0.0
    rmse:             float = 0.0
    # Facteurs saisonniers F(n,k) — UNIQUEMENT pour HW, liste vide pour MA et LES
    seasonal_factors: List[float] = field(default_factory=list)
    alerts:           List[str]   = field(default_factory=list)


@dataclass
class CompareResult:
    methods:             Dict[str, ForecastResult]
    best_statistical:    str
    recommended:         str
    verdict:             str
    seasonal_detected:   bool
    season_len:          int
    cv:                  float
    trend:               float
    trend_pct:           float
    n:                   int
    manager_note:        str = ""


# ─────────────────────────────────────────────────────────────────────────────
# PRÉ-TRAITEMENT
# ─────────────────────────────────────────────────────────────────────────────

def _clean(v: np.ndarray) -> np.ndarray:
    """Nettoie la série : NaN/inf → interpolation, zéros isolés → interpolation."""
    v = np.array(v, dtype=float)
    v[~np.isfinite(v)] = np.nan
    nans = np.isnan(v)
    if nans.all():
        return np.zeros(len(v))
    if nans.any():
        idx = np.arange(len(v))
        v = np.interp(idx, idx[~nans], v[~nans])
    for i in range(1, len(v) - 1):
        if v[i] == 0 and v[i-1] > 0 and v[i+1] > 0:
            v[i] = (v[i-1] + v[i+1]) / 2
    return v


def _metrics(actual: np.ndarray, fitted: np.ndarray) -> Tuple[float, float, float]:
    """
    MAE, MAPE (sur valeurs > 0), RMSE — calculés ex-ante sur les périodes 1..n.
    RÈGLE : le MAPE le plus BAS indique la méthode la plus précise.
    La période 0 est exclue (initialisation, pas d'erreur ex-ante possible).
    """
    if len(actual) < 2:
        return 0.0, 0.0, 0.0
    a = actual[1:]
    f = fitted[1:]
    err  = a - f
    mae  = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mask = a > 0
    mape = float(np.mean(np.abs(err[mask] / a[mask])) * 100) if mask.any() else 999.0
    return round(mae, 2), round(mape, 2), round(rmse, 2)


def _intervals(forecast: np.ndarray, rmse: float,
               z: float = 1.44) -> Tuple[np.ndarray, np.ndarray]:
    """
    Intervalles de confiance à ~85% (z=1.44), croissants avec l'horizon.
    Formule : Prévision ± z × RMSE × √horizon
    Interprétation : dans ~85% des cas, la demande réelle tombera dans [bas, haut].
    """
    h = np.arange(1, len(forecast) + 1)
    margin = z * rmse * np.sqrt(h)
    lo = np.maximum(0, np.round(forecast - margin, 0))
    hi = np.round(forecast + margin, 0)
    return lo, hi


# ─────────────────────────────────────────────────────────────────────────────
# DÉTECTION SAISONNALITÉ (utilisée par HW uniquement)
# ─────────────────────────────────────────────────────────────────────────────

def _test_season(v: np.ndarray, s: int) -> float:
    """Score de saisonnalité = variance inter-positions / variance totale."""
    n = len(v)
    n_full = (n // s) * s
    if n_full < s * 2:
        return 0.0
    mat = v[:n_full].reshape(-1, s)
    var_total = np.var(v)
    if var_total < 1e-9:
        return 0.0
    return float(np.var(mat.mean(axis=0)) / var_total)


def detect_season(v: np.ndarray) -> int:
    """
    Détecte le cycle saisonnier le plus probable parmi [2,3,4,6,12,24,52].
    Retourne 0 si aucune saisonnalité significative (seuil = 0.15).
    Utilisé uniquement pour orienter HW.
    """
    n = len(v)
    candidates = [s for s in [2, 3, 4, 6, 12, 24, 52] if n >= s * 2]
    if not candidates:
        return 0
    scores = {s: _test_season(v, s) for s in candidates}
    best_s, best_score = max(scores.items(), key=lambda x: x[1])
    return best_s if best_score > 0.15 else 0


# ─────────────────────────────────────────────────────────────────────────────
# MÉTHODE 1 : MOYENNE MOBILE (MA)
# ─────────────────────────────────────────────────────────────────────────────

def moving_average(history: np.ndarray, window: int = None,
                   n_forecast: int = 6) -> ForecastResult:
    """
    Moyenne Mobile — fenêtre w optimisée automatiquement sur [2..12].
    
    ⚠ IMPORTANT : MA n'utilise PAS α, β ou γ.
    Ces paramètres appartiennent au lissage exponentiel (LES, HW).
    MA calcule simplement la moyenne des w dernières valeurs observées.
    
    Sélection : fenêtre w minimisant le MAPE (ex-ante, sans biais).
    fitted[t] = moyenne de v[t-w .. t-1]  (prévision AVANT d'observer v[t])
    """
    v = _clean(history)
    n = len(v)
    if n < 2:
        return ForecastResult(method="MA", alerts=["Historique trop court (n<2)."])

    max_w = max(2, min(n // 2, 12))
    best_w, best_mape = 2, np.inf

    for w in range(2, max_w + 1):
        # Calcul ex-ante : fitted[t] = moyenne des w périodes PRÉCÉDENTES
        fitted = np.array([
            np.mean(v[max(0, i - w):i]) if i >= w else v[0]
            for i in range(n)
        ])
        _, mape, _ = _metrics(v, fitted)
        # RÈGLE : on MINIMISE le MAPE → fenêtre retenue = celle avec MAPE le plus bas
        if mape < best_mape:
            best_mape, best_w = mape, w

    if window is not None:
        best_w = max(2, min(int(window), max_w))

    fitted = np.array([
        np.mean(v[max(0, i - best_w):i]) if i >= best_w else v[0]
        for i in range(n)
    ])
    mae, mape, rmse = _metrics(v, fitted)
    fc = np.full(n_forecast, float(np.mean(v[-best_w:])))
    lo, hi = _intervals(fc, rmse)

    alerts = []
    if mape > 30:
        alerts.append(
            f"MA(w={best_w}) MAPE={mape:.1f}% élevé — série trop volatile pour MA. "
            "Essayez LES ou HW."
        )

    return ForecastResult(
        method=f"MA(w={best_w})",
        alpha=0.0, beta=0.0, gamma=0.0,   # MA n'a pas ces paramètres
        season_len=0, n_history=n,
        fitted=fitted, forecast=fc,
        intervals_low=lo, intervals_high=hi,
        mae=mae, mape=mape, rmse=rmse,
        seasonal_factors=[],               # facteurs saisonniers = HW uniquement
        alerts=alerts
    )


# ─────────────────────────────────────────────────────────────────────────────
# MÉTHODE 2 : LES — Lissage Exponentiel Simple
# ─────────────────────────────────────────────────────────────────────────────

def les(history: np.ndarray, alpha: float = None,
        n_forecast: int = 6) -> ForecastResult:
    """
    Lissage Exponentiel Simple — un seul paramètre : α (alpha).
    
    Paramètre α (alpha) — contrôle la réactivité au niveau :
      α proche de 1 → très réactif (suit la dernière valeur observée)
      α proche de 0 → très stable (lisse les variations, privilégie l'historique long)
      Valeur typique : 0.1 à 0.4 pour des séries industrielles
    
    ⚠ LES n'a PAS de β ni γ — ces paramètres appartiennent à HW.
    ⚠ LES n'a PAS de facteurs saisonniers F(n,k) — réservés à HW.
    
    Optimisation : α retenu = celui qui MINIMISE le MAPE (ex-ante).
    fitted[t] = S[t-1]  (prévision faite AVANT d'observer la valeur t)
    """
    v = _clean(history)
    n = len(v)
    if n < 2:
        return ForecastResult(method="LES", alerts=["Historique trop court (n<2)."])

    def _fit(a: float) -> Tuple[np.ndarray, np.ndarray]:
        S = np.empty(n)
        S[0] = v[0]
        for i in range(1, n):
            S[i] = a * v[i] + (1 - a) * S[i-1]
        # Ex-ante : fitted[t] = S[t-1] (prévision AVANT observation de v[t])
        fitted = np.empty(n)
        fitted[0] = S[0]
        fitted[1:] = S[:-1]
        return S, fitted

    if alpha is None:
        best_a, best_mape = 0.3, np.inf
        for a in np.round(np.arange(0.05, 1.0, 0.05), 2):
            _, fitted = _fit(float(a))
            _, mape, _ = _metrics(v, fitted)
            # RÈGLE : on MINIMISE le MAPE → α retenu = celui avec MAPE le plus bas
            if mape < best_mape:
                best_mape, best_a = mape, float(a)
        alpha = best_a

    S, fitted = _fit(alpha)
    mae, mape, rmse = _metrics(v, fitted)
    fc = np.full(n_forecast, float(S[-1]))
    lo, hi = _intervals(fc, rmse)

    alerts = []
    if n >= 4:
        tr = abs(float(np.polyfit(np.arange(n), v, 1)[0]))
        mv = float(np.mean(v))
        if mv > 0 and tr / mv > 0.15:
            alerts.append(
                f"LES : tendance détectée ({tr:+.2f}/période). "
                "Holt-Winters capture mieux les tendances et la saisonnalité."
            )

    return ForecastResult(
        method="LES",
        alpha=round(alpha, 2),
        beta=0.0,    # LES n'a pas de β
        gamma=0.0,   # LES n'a pas de γ
        season_len=0, n_history=n,
        fitted=fitted, forecast=fc,
        intervals_low=lo, intervals_high=hi,
        mae=mae, mape=mape, rmse=rmse,
        seasonal_factors=[],   # facteurs saisonniers = HW uniquement
        alerts=alerts
    )


# ─────────────────────────────────────────────────────────────────────────────
# MÉTHODE 3 : HOLT-WINTERS ADDITIF (HW)
# ─────────────────────────────────────────────────────────────────────────────

def holt_winters(history: np.ndarray, season_len: int = None,
                 alpha: float = None, beta: float = None, gamma: float = None,
                 n_forecast: int = 6) -> ForecastResult:
    """
    Holt-Winters Additif — niveau + tendance + saisonnalité F(n,k).
    Grille d'optimisation 5×5×5 = 125 combinaisons.
    
    Paramètres — TOUS trois nécessaires pour HW :
      α (alpha) — réactivité au niveau (0.05–0.95)
        Élevé → suit les variations récentes de la demande
        Faible → lisse les variations, privilégie la tendance long terme
      β (beta)  — réactivité à la tendance (0.05–0.50)
        Élevé → s'adapte vite aux accélérations/décélérations
        Faible → tendance stable, ignore les variations ponctuelles
      γ (gamma) — réactivité aux facteurs saisonniers F(n,k) (0.05–0.50)
        Élevé → les coefficients saisonniers s'actualisent rapidement
        Faible → cycles saisonniers stables, lissés sur plusieurs années
    
    Facteurs saisonniers F(n,k) — EXCLUSIFS à HW :
      F(n,k) représente l'écart récurrent de la période k du cycle n
      par rapport à la moyenne. Ex : F=1.25 → ce mois est 25% au-dessus
      de la moyenne annuelle. MA et LES n'ont pas de facteurs saisonniers.
    
    Optimisation : combinaison (α, β, γ) retenue = celle qui MINIMISE le MAPE.
    Repli sur LES si données insuffisantes (< 2 cycles complets).
    """
    v = _clean(history)
    n = len(v)

    if season_len is None:
        season_len = detect_season(v)

    if season_len < 2 or n < season_len * 2:
        # Pas assez de données pour HW → repli sur LES
        result = les(v, alpha=alpha, n_forecast=n_forecast)
        result.method = "HW→LES"
        result.alerts.append(
            f"HW : données insuffisantes (n={n} < {season_len*2 if season_len>0 else 'min'} requises). "
            "Repli sur LES."
            if season_len > 0 else
            "HW : aucune saisonnalité détectée. Repli sur LES."
        )
        return result

    def _init_S(s: int) -> np.ndarray:
        n_full = (n // s) * s
        grand_mn = np.mean(v[:n_full])
        return np.array([np.mean(v[j:n_full:s]) - grand_mn for j in range(s)])

    def _fit(a: float, b: float, g: float
             ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        S = _init_S(season_len).copy()
        L = np.empty(n); T = np.empty(n); fitted = np.empty(n)

        if n >= season_len:
            slope0 = float(np.polyfit(np.arange(season_len), v[:season_len], 1)[0])
            L[0] = v[0] - S[0]; T[0] = slope0
        else:
            L[0] = v[0]; T[0] = 0.0
        fitted[0] = L[0] + T[0] + S[0]

        for i in range(1, n):
            j      = i % season_len
            prev_S = S[j]
            new_L  = a * (v[i] - prev_S) + (1 - a) * (L[i-1] + T[i-1])
            T[i]   = b * (new_L - L[i-1]) + (1 - b) * T[i-1]
            S[j]   = g * (v[i] - new_L)   + (1 - g) * prev_S
            L[i]   = new_L
            # Ex-ante : prévision faite avec L[i-1], T[i-1], S AVANT mise à jour
            fitted[i] = L[i-1] + T[i-1] + prev_S

        fc = np.array([
            L[-1] + T[-1] * (h + 1) + S[(n + h) % season_len]
            for h in range(n_forecast)
        ])
        return L, T, S, fitted, np.maximum(0, fc)

    if any(p is None for p in [alpha, beta, gamma]):
        best_a, best_b, best_g, best_mape = 0.3, 0.1, 0.1, np.inf
        # RÈGLE : on MINIMISE le MAPE → combinaison retenue = celle avec MAPE le plus bas
        for a in [0.1, 0.25, 0.4, 0.6, 0.8]:
            for b in [0.05, 0.1, 0.2, 0.35, 0.5]:
                for g in [0.05, 0.1, 0.2, 0.35, 0.5]:
                    try:
                        _, _, _, fitted, _ = _fit(a, b, g)
                        _, mape, _ = _metrics(v, fitted)
                        if mape < best_mape:
                            best_mape, best_a, best_b, best_g = mape, a, b, g
                    except:
                        continue
        alpha = alpha if alpha is not None else best_a
        beta  = beta  if beta  is not None else best_b
        gamma = gamma if gamma is not None else best_g

    L, T, S_final, fitted, fc = _fit(alpha, beta, gamma)
    mae, mape, rmse = _metrics(v, fitted)
    lo, hi = _intervals(fc, rmse)

    # Facteurs saisonniers F(n,k) — EXCLUSIFS à HW
    seasonal_factors = [round(float(x), 4) for x in S_final]

    alerts = []
    if mape > 25:
        alerts.append(
            f"HW MAPE={mape:.1f}% élevé — vérifier la qualité de l'historique "
            f"(au moins {season_len * 3} périodes recommandées)."
        )

    return ForecastResult(
        method="Holt-Winters",
        alpha=round(alpha, 2),
        beta=round(beta, 2),
        gamma=round(gamma, 2),
        season_len=season_len,
        n_history=n,
        fitted=fitted, forecast=fc,
        intervals_low=lo, intervals_high=hi,
        mae=mae, mape=mape, rmse=rmse,
        seasonal_factors=seasonal_factors,
        alerts=alerts
    )


# Alias conservé pour compatibilité avec parsers.py et app.py
def mbs(history: np.ndarray, alpha: float = None, beta: float = None,
        n_forecast: int = 6) -> ForecastResult:
    """
    Alias de compatibilité — redirige vers LES.
    MBS/Holt a été retiré pour éviter la confusion avec MA (Moyenne Mobile).
    La gradation est désormais : MA → LES → HW.
    """
    return les(history, alpha=alpha, n_forecast=n_forecast)


# ─────────────────────────────────────────────────────────────────────────────
# COMPARAISON + VERDICT MÉTIER
# ─────────────────────────────────────────────────────────────────────────────

# Seuil minimum de gain pour préférer HW à LES (points de MAPE)
# Si gain HW vs LES < SEUIL_MIN_GAIN → LES préféré (plan de production plus stable)
SEUIL_MIN_GAIN = 2.0

def compare_all(history: np.ndarray, n_forecast: int = 6,
                ma_window: int = None) -> CompareResult:
    """
    Lance MA, LES et HW, optimise automatiquement (sans lookahead bias),
    puis applique les règles métier S&OP.
    
    RÈGLE DE SÉLECTION — MINIMISER l'erreur (MAPE) :
      → La méthode avec le MAPE le PLUS BAS est la plus précise.
      → Le MAPE est toujours calculé ex-ante (sans biais lookahead).
      → Un MAPE de 5% = erreur moyenne de 5% vs demande réelle.
    
    Règles métier (appliquées APRÈS la sélection statistique) :
      R0 : n < 4  → MA uniquement
      R1 : n < 8  → MA + LES uniquement
      R2 : Saisonnalité ET gain HW > SEUIL_MIN_GAIN (2 pts) → HW
           Sinon : LES recommandé pour la stabilité du plan de production
      R3 : CV > 60% → alerte risque élevé (toute méthode peu fiable)
      R4 : Tendance forte (> 15%) → HW avec β pour capter la tendance
    """
    v = _clean(history)
    n = len(v)

    mean_v    = float(np.mean(v)) if n > 0 else 1.0
    std_v     = float(np.std(v))
    cv        = round(std_v / mean_v * 100, 1) if mean_v > 0 else 0.0
    trend     = round(float(np.polyfit(np.arange(n), v, 1)[0]), 4) if n >= 3 else 0.0
    trend_pct = round(abs(trend) / mean_v * 100, 1) if mean_v > 0 else 0.0
    s_len     = detect_season(v)
    seasonal  = s_len > 0

    results: Dict[str, ForecastResult] = {}

    # R0 : historique trop court
    if n < 4:
        results["MA"] = moving_average(v, window=ma_window, n_forecast=n_forecast)
        return CompareResult(
            methods=results, best_statistical="MA", recommended="MA",
            verdict=f"Historique très court ({n} périodes). Seule MA est utilisable.",
            seasonal_detected=False, season_len=0, cv=cv,
            trend=trend, trend_pct=trend_pct, n=n,
            manager_note="Collectez au moins 8 périodes pour utiliser LES, 24+ pour HW."
        )

    # R1 : historique court
    if n < 8:
        results["MA"]  = moving_average(v, window=ma_window, n_forecast=n_forecast)
        results["LES"] = les(v, n_forecast=n_forecast)
        # SÉLECTION : MAPE le plus BAS
        best = min(results, key=lambda k: results[k].mape)
        return CompareResult(
            methods=results, best_statistical=best, recommended=best,
            verdict=(
                f"Historique court ({n} périodes). {best} recommandé "
                f"(MAPE={results[best].mape:.1f}% — plus bas = plus précis). "
                f"Collectez ≥ {s_len*2 if s_len>0 else 24} périodes pour HW."
            ),
            seasonal_detected=False, season_len=0, cv=cv,
            trend=trend, trend_pct=trend_pct, n=n,
            manager_note="Collectez au moins 24 périodes pour utiliser Holt-Winters."
        )

    # Calcul des 3 méthodes
    results["MA"]  = moving_average(v, window=ma_window, n_forecast=n_forecast)
    results["LES"] = les(v, n_forecast=n_forecast)
    results["HW"]  = holt_winters(
        v, season_len=s_len if s_len > 0 else None,
        n_forecast=n_forecast
    )

    # SÉLECTION STATISTIQUE : méthode avec MAPE le plus BAS
    best_stat   = min(results, key=lambda k: results[k].mape)
    recommended = best_stat
    reasons: List[str] = []

    # R2 : Saisonnalité → HW si gain significatif, LES sinon
    if seasonal and "HW" in results:
        hw_mape  = results["HW"].mape
        les_mape = results["LES"].mape
        best_mape = results[best_stat].mape
        # Gain = combien on GAGNE en passant à HW (positif = HW meilleur)
        gain_hw  = round(les_mape - hw_mape, 1)

        if hw_mape <= best_mape * 1.10:
            if gain_hw < SEUIL_MIN_GAIN:
                # Gain insuffisant → LES pour la stabilité du plan
                recommended = "LES"
                reasons.append(
                    f"Saisonnalité détectée (cycle={s_len} périodes) mais gain HW négligeable "
                    f"(+{gain_hw:.1f}% vs LES — seuil={SEUIL_MIN_GAIN}%). "
                    f"LES recommandé pour la stabilité du plan de production : "
                    f"cadences stables, moins de variabilité."
                )
            else:
                # Gain significatif → HW justifié
                recommended = "HW"
                reasons.append(
                    f"Saisonnalité détectée (cycle={s_len} périodes) et gain significatif "
                    f"HW vs LES : MAPE {hw_mape:.1f}% vs {les_mape:.1f}% "
                    f"(gain = {gain_hw:.1f}% > seuil {SEUIL_MIN_GAIN}%). "
                    f"Holt-Winters recommandé : les facteurs saisonniers F(n,k) "
                    f"capturent les pics récurrents."
                )
        else:
            reasons.append(
                f"Saisonnalité détectée (cycle={s_len}) mais HW moins performant "
                f"(MAPE={results['HW'].mape:.1f}% > {best_stat}={results[best_stat].mape:.1f}%). "
                f"Méthode {best_stat} retenue."
            )

    # R3 : tendance forte → HW (avec β pour la capter)
    if recommended not in ("HW",) and trend_pct > 15 and "HW" in results:
        hw_mape  = results["HW"].mape
        les_mape = results["LES"].mape
        if hw_mape <= les_mape * 1.08:
            recommended = "HW"
            reasons.append(
                f"Tendance significative {trend:+.2f}/période ({trend_pct:.0f}% de la moyenne). "
                f"HW/Holt-Winters recommandé pour sa composante β (tendance). "
                f"MAPE HW={hw_mape:.1f}% vs LES={les_mape:.1f}%."
            )

    if not reasons:
        reasons.append(
            f"Aucune saisonnalité ni tendance dominante. "
            f"{best_stat} recommandé (MAPE={results[best_stat].mape:.1f}% — "
            f"valeur la plus basse parmi les méthodes testées)."
        )

    # Alerte CV élevé
    cv_alert = ""
    if cv > 60:
        cv_alert = (
            f" | ⚠ ALERTE : CV={cv:.1f}% — série très volatile. "
            f"Toute méthode de prévision sera imprécise sur cette série. "
            f"Envisagez de segmenter la demande ou d'élargir les intervalles de confiance."
        )

    r = results[recommended]
    # Paramètres affichés selon la méthode
    if recommended == "MA":
        params_str = f"fenêtre={r.method.split('w=')[1].rstrip(')')} (aucun α/β/γ)"
    elif recommended == "LES":
        params_str = f"α={r.alpha} (β et γ non applicables à LES)"
    else:  # HW
        params_str = f"α={r.alpha}, β={r.beta}, γ={r.gamma}, cycle={r.season_len}"

    reasons.append(f"Paramètres optimaux : {params_str}.")
    verdict = " ".join(reasons) + cv_alert

    # ── Note manager — explication en langage naturel ───────────────────────
    les_r = results.get("LES")
    rec_r = results[recommended]
    if les_r and recommended != "LES" and les_r.mape > 0:
        gain = round(les_r.mape - rec_r.mape, 1)
        if gain < SEUIL_MIN_GAIN:
            manager_note = (
                f"Note Manager : {recommended} est mathématiquement plus précis de {gain:.1f}% "
                f"seulement (en dessous du seuil de {SEUIL_MIN_GAIN}%). "
                f"LES est préféré pour un plan de production stable — "
                f"les cadences varient moins, la gestion des ateliers est simplifiée."
            )
        elif gain < 5:
            manager_note = (
                f"Note Manager : {recommended} apporte un gain de {gain:.1f}% vs LES. "
                f"Gain modéré — à utiliser si votre production absorbe facilement "
                f"des variations de cadence mensuelles."
            )
        else:
            manager_note = (
                f"Note Manager : {recommended} apporte un gain significatif de {gain:.1f}% "
                f"vs LES. Recommandé si la précision est critique "
                f"(produits à forte valeur, délais longs, risque rupture élevé)."
            )
    elif recommended == "LES":
        manager_note = (
            "Note Manager : LES est la méthode la plus adaptée à cette série. "
            "Plan de production stable — aucune variation de cadence inutile."
        )
    else:
        manager_note = (
            f"Note Manager : {recommended} est la méthode la plus adaptée. "
            "Paramètres optimisés automatiquement pour minimiser l'erreur de prévision."
        )

    return CompareResult(
        methods=results,
        best_statistical=best_stat,
        recommended=recommended,
        verdict=verdict,
        seasonal_detected=seasonal,
        season_len=s_len,
        cv=cv, trend=trend, trend_pct=trend_pct, n=n,
        manager_note=manager_note
    )


# ─────────────────────────────────────────────────────────────────────────────
# WHAT-IF DEMANDE
# ─────────────────────────────────────────────────────────────────────────────

def whatif_demand(history: np.ndarray, scenario: str,
                  alpha: float = None, beta: float = None,
                  gamma: float = None, ma_window: int = None,
                  n_forecast: int = 6) -> dict:
    """
    Scénarios What-if demande — compare la méthode demandée vs recommandée.
    
    ERP (référence) : prévision issue du système ERP de l'entreprise (fichier importé).
    Toutes les erreurs sont calculées ex-ante (sans biais lookahead).
    La méthode retenue est celle qui MINIMISE le MAPE.
    
    Paramètres affichés selon la méthode :
      MA  → fenêtre uniquement (pas de α/β/γ)
      LES → α uniquement
      HW  → α, β, γ
    """
    v = _clean(history)
    ref_cmp = compare_all(v, n_forecast)
    ref     = ref_cmp.methods[ref_cmp.recommended]

    dispatch = {
        "MA":        lambda: moving_average(v, window=ma_window, n_forecast=n_forecast),
        "LES":       lambda: les(v, alpha=alpha, n_forecast=n_forecast),
        # MBS supprimé — redirige vers LES pour compatibilité
        "MBS":       lambda: les(v, alpha=alpha, n_forecast=n_forecast),
        "HW":        lambda: holt_winters(v, alpha=alpha, beta=beta, gamma=gamma, n_forecast=n_forecast),
        "LES_alpha": lambda: les(v, alpha=alpha, n_forecast=n_forecast),
        "MBS_alpha": lambda: les(v, alpha=alpha, n_forecast=n_forecast),
        "MBS_beta":  lambda: les(v, alpha=alpha, n_forecast=n_forecast),
        "HW_gamma":  lambda: holt_winters(v, alpha=alpha, beta=beta, gamma=gamma, n_forecast=n_forecast),
    }
    scen = dispatch.get(scenario, lambda: les(v, n_forecast=n_forecast))()

    delta_mape = round(scen.mape - ref.mape, 2)
    delta_fc   = [round(float(scen.forecast[i] - ref.forecast[i]), 0) for i in range(n_forecast)]

    # RÈGLE : MAPE le plus bas = meilleure méthode
    if delta_mape < -2:
        verdict = "AMELIORATION"        # scénario RÉDUIT l'erreur → meilleur
    elif delta_mape <= 2:
        verdict = "EQUIVALENT"
    elif delta_mape <= 5:
        verdict = "LEGER RECUL"         # scénario AUGMENTE l'erreur → moins bon
    else:
        verdict = "DEGRADATION"         # scénario fortement moins bon

    if scenario in ("HW", "DEM_HW") and ref_cmp.seasonal_detected and delta_mape < 10:
        verdict = "RECOMMANDE (saisonnalite capturee)"
    elif scenario in ("HW", "DEM_HW") and not ref_cmp.seasonal_detected:
        verdict = "DECONSEILLE (serie non saisonniere)"
    elif scenario in ("LES", "DEM_LES", "LES_alpha") and ref_cmp.seasonal_detected and ref_cmp.recommended == "HW":
        verdict = "RISQUE (perte saisonnalite)"

    return {
        "reference": ref, "scenario": scen,
        "delta_mape": delta_mape, "delta_forecast": delta_fc,
        "verdict": verdict, "ref_compare": ref_cmp,
    }


# ─────────────────────────────────────────────────────────────────────────────
# WHAT-IF PRODUCTION
# ─────────────────────────────────────────────────────────────────────────────

def whatif_production(prod_data, scenario: str, value: float = None):
    """Modifie ProductionData selon le scénario. Retourne une copie modifiée."""
    mod = deepcopy(prod_data)
    p   = mod.params

    if scenario == "cap_minus_20":
        for per in mod.periods:
            mod.capacity[per] = round(prod_data.capacity.get(per, p["cap_v"]) * 0.80, 2)
        p["cap_v"] = round(p["cap_v"] * 0.80, 2)
    elif scenario == "cap_plus_15":
        for per in mod.periods:
            mod.capacity[per] = round(prod_data.capacity.get(per, p["cap_v"]) * 1.15, 2)
        p["cap_v"] = round(p["cap_v"] * 1.15, 2)
    elif scenario == "cap_ignored":
        for per in mod.periods:
            mod.capacity[per] = 999_999.0
        p["cap_v"] = 999_999.0
    elif scenario == "minprod" and value is not None:
        for per in mod.periods:
            mod.min_prod[per] = float(value)
    elif scenario == "cap_value" and value is not None:
        for per in mod.periods:
            mod.capacity[per] = float(value)
        p["cap_v"] = float(value)

    p["max_u"] = round(p["cap_v"] / p["var_v"], 0) if p.get("var_v", 0) > 0 else p["cap_v"]
    return mod