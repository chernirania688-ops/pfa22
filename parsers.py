"""
parsers.py — Normalisation universelle des fichiers Excel
Transforme n'importe quel Excel vers un format interne stable.
"""
import pandas as pd
import numpy as np
import re


def cn(v) -> float:
    if v is None: return 0.0
    if isinstance(v, (int, float)):
        return float(v) if not (isinstance(v, float) and np.isnan(v)) else 0.0
    try:
        return float(str(v).strip().replace(" ", "").replace(",", "."))
    except:
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# FORMAT INTERNE STABLE
# ══════════════════════════════════════════════════════════════════════════════
class ProductionData:
    """Format interne normalisé pour la production."""
    def __init__(self):
        self.periods: list = []          # ["W34 Y23", "W35 Y23", ...]
        self.gross_req: dict = {}        # {period: float}
        self.capacity: dict = {}         # {period: float}  [PHR]
        self.var_req: dict = {}          # {period: float}  [PHR/U]
        self.safety_stock: dict = {}     # {period: float}
        self.min_prod: dict = {}         # {period: float}
        self.prod_plan: dict = {}        # {period: float}
        self.batch: dict = {}            # {period: float}
        self.init_inv: dict = {}         # {period: float}
        self.params: dict = {}           # cap_v, var_v, max_u, ss_v, inv0


class DemandData:
    """Format interne normalisé pour la demande."""
    def __init__(self):
        self.articles: dict = {}         # {art_id: {"history": Series, "forecast_erp": Series}}
        self.kpis: dict = {}             # {art_id: {"mape": float, "mae": float, "rmse": float}}
        self.periods: list = []          # liste des périodes


# ══════════════════════════════════════════════════════════════════════════════
# PARSER PRODUCTION
# ══════════════════════════════════════════════════════════════════════════════
def load_production_excel(dfs: dict) -> ProductionData:
    """
    Charge n'importe quel fichier production Excel.
    Supporte :
    - Format standard (Donnees/Data field + colonnes semaines)
    - Format libre (lignes labellisées)
    """
    data = ProductionData()
    df = None; lc = None

    # Détection colonne label
    LABEL_KEYWORDS = ("donnees", "data field", "data fields", "label",
                      "description", "libelle", "parametre", "row")
    for d in dfs.values():
        for c in d.columns:
            if str(c).lower() in LABEL_KEYWORDS:
                df = d; lc = c; break
        if df is not None: break

    # Fallback : colonne avec le plus de texte
    if df is None:
        for d in dfs.values():
            str_cols = [c for c in d.columns if d[c].dtype == object]
            if len(str_cols) >= 1:
                df = d
                # Choisit la colonne avec le plus de valeurs non-numériques
                best = max(str_cols, key=lambda c: sum(
                    1 for v in d[c] if isinstance(v, str) and len(v) > 3))
                lc = best
                break
    if df is None:
        df = list(dfs.values())[0]
        lc = df.columns[min(1, len(df.columns) - 1)]

    # Périodes = colonnes qui ressemblent à des semaines/dates/trimestres
    skip = {str(df.columns[0]), str(lc), "Resource", "resource", "NaN", "nan", ""}
    periods = [c for c in df.columns
               if str(c).strip() not in skip
               and not str(c).lower().startswith("unnamed")
               and not str(c).lower().startswith("nan")]

    data.periods = [str(p) for p in periods]

    # Mapping flexible des lignes
    MAPPINGS = {
        "gross": ["gross", "besoin", "demand", "requirement", "req"],
        "capacity": ["capacity", "capacit", "cap", "available", "disponible"],
        "var_req": ["variable", "var_req", "taux", "rate", "phr/u"],
        "safety": ["safety", "securit", "stock securit", "ss"],
        "min_prod": ["minimum production", "min prod", "min_prod", "minimum plan"],
        "prod_plan": ["production plan", "plan", "frozen", "planif"],
        "batch": ["batch", "lot", "taille"],
        "init_inv": ["initial", "inventaire", "stock initial", "opening"],
    }

    def find_row(keywords):
        for _, row in df.iterrows():
            label = str(row[lc]).lower()
            if any(kw in label for kw in keywords):
                return {p: cn(row[p]) for p in periods}
        return {p: 0.0 for p in periods}

    data.gross_req    = find_row(MAPPINGS["gross"])
    data.capacity     = find_row(MAPPINGS["capacity"])
    data.var_req      = find_row(MAPPINGS["var_req"])
    data.safety_stock = find_row(MAPPINGS["safety"])
    data.min_prod     = find_row(MAPPINGS["min_prod"])
    data.prod_plan    = find_row(MAPPINGS["prod_plan"])
    data.batch        = find_row(MAPPINGS["batch"])
    data.init_inv     = find_row(MAPPINGS["init_inv"])

    def fp(d): return next((cn(v) for v in d.values() if cn(v) > 0), 0.0)
    cap_v = fp(data.capacity) or 1400.0
    var_v = fp(data.var_req)  or 0.4667
    bat_v = fp(data.batch)    or 1.0
    ss_v  = fp(data.safety_stock) or 0.0
    inv0  = fp(data.init_inv) or 0.0
    max_u = round(cap_v / var_v, 0) if var_v > 0 else 0.0

    data.params = {
        "cap_v": cap_v, "var_v": var_v, "bat_v": bat_v,
        "ss_v": ss_v, "inv0": inv0, "max_u": max_u,
    }
    return data


# ══════════════════════════════════════════════════════════════════════════════
# PARSER DEMANDE
# ══════════════════════════════════════════════════════════════════════════════
def load_demand_excel(dfs: dict) -> DemandData:
    """
    Charge n'importe quel fichier demande Excel.
    Supporte :
    - Format article_report_merged (Series + KPIs)
    - Format LES/HW/MBS (colonne Demande + données numériques)
    - Format générique (colonnes numériques temporelles)
    """
    data = DemandData()
    df_s = df_k = None

    for sh, d in dfs.items():
        sl = sh.lower()
        if "series" in sl or "serie" in sl: df_s = d
        elif "kpi" in sl or "compare" in sl: df_k = d

    # ── FORMAT 1 : article_report_merged ────────────────────────────────────
    if df_s is not None and df_s.shape[1] > 10:
        ac = df_s.columns[0]; fc = df_s.columns[1]
        tc = [c for c in df_s.columns
              if c not in [ac, fc] and not str(c).lower().startswith("unnamed")]
        data.periods = [str(c) for c in tc]
        arts = {}; cur = None
        for _, row in df_s.iterrows():
            av = str(row[ac]).strip()
            if av and av.lower() not in ("nan", ""): cur = av
            if not cur: continue
            arts.setdefault(cur, {})[str(row[fc]).strip()] = pd.Series(
                [cn(row[c]) for c in tc], index=tc, dtype=float)
        for art, fields in arts.items():
            hk = next((k for k in fields if "calculation history" in k.lower()), None)
            sk = next((k for k in fields if "statistical" in k.lower()
                       and "forecast" in k.lower()), None)
            if hk is None: continue
            h = fields[hk].dropna(); h = h[h > 0]
            if len(h) < 3: continue
            data.articles[art] = {
                "history": h,
                "forecast_erp": fields[sk].dropna() if sk else pd.Series(dtype=float),
            }
            if df_k is not None:
                kr = df_k[df_k[df_k.columns[0]].astype(str)
                          .str.contains(art[:10], na=False, case=False)]
                if not kr.empty:
                    data.kpis[art] = {
                        "mae":  cn(kr.iloc[0].iloc[1]),
                        "mape": cn(kr.iloc[0].iloc[2]),
                        "rmse": cn(kr.iloc[0].iloc[3]) if len(kr.iloc[0]) > 3 else 0.0,
                    }
        if data.articles:
            return data

    # ── FORMAT 2 : LES/HW/MBS — colonne "Demande" avec extraction précise ─────
    for sh, df in dfs.items():
        df_raw = df.reset_index(drop=True)
        header_row = None
        # Cherche la ligne header (contient "Demande" ou "Demand")
        for i in range(min(8, len(df_raw))):
            row_str = ' '.join(str(v) for v in df_raw.iloc[i]).lower()
            if 'demande' in row_str or 'demand' in row_str:
                header_row = i; break
        if header_row is None:
            continue

        # Identifie la colonne "Demande" et la colonne "période/trimestre"
        header_vals = [str(v).strip() for v in df_raw.iloc[header_row]]
        dem_col_idx = next(
            (j for j, h in enumerate(header_vals)
             if ('demande' in h.lower() or 'demand' in h.lower())
             and 'unnamed' not in h.lower()),
            None)
        if dem_col_idx is None:
            continue

        # Colonne période = première colonne numérique à gauche de Demande
        period_col_idx = next(
            (j for j in range(dem_col_idx)
             if any(cn(df_raw.iloc[r, j]) is not None
                    for r in range(header_row+1, min(header_row+5, len(df_raw))))),
            None)

        art_name = f"{sh} — {header_vals[dem_col_idx]}"
        series_vals = []

        # Extraction ligne par ligne : STOP dès qu'il n'y a plus de valeur numérique
        # dans la colonne Demande (évite de lire les formules de calcul suivantes)
        for r in range(header_row + 1, len(df_raw)):
            d_val = cn(df_raw.iloc[r, dem_col_idx])
            if d_val is None:
                # Vérifie si c'est vraiment la fin (pas un trou isolé)
                # Si 2 NaN consécutifs → fin de la série
                if r + 1 < len(df_raw) and cn(df_raw.iloc[r+1, dem_col_idx]) is None:
                    break
                continue
            if d_val <= 0:
                break
            # Si colonne période disponible, vérifie que la ligne est bien dans la série
            if period_col_idx is not None:
                p_val = cn(df_raw.iloc[r, period_col_idx])
                # Stop si la colonne période est vide et qu'on a déjà des valeurs
                # (signifie qu'on sort de la plage de données)
                if p_val is None and len(series_vals) > 0:
                    # Autorise quelques lignes sans période (cas HW avec Année fusionnée)
                    pass
            series_vals.append(d_val)

        if len(series_vals) >= 3:
            data.articles[art_name] = {
                "history": pd.Series(np.array(series_vals), name=art_name),
                "forecast_erp": pd.Series(dtype=float),
            }
            data.periods = list(range(len(series_vals)))

    # ── FORMAT 3 : colonnes numériques temporelles ───────────────────────────
    if not data.articles:
        for sh, df in dfs.items():
            num_cols = [c for c in df.columns
                       if df[c].dtype in [np.float64, np.int64]
                       and df[c].dropna().shape[0] >= 3
                       and not str(c).lower().startswith("unnamed")]
            for nc in num_cols[:4]:
                series = df[nc].apply(cn).dropna()
                series = series[series > 0]
                if len(series) >= 3:
                    art_name = f"{sh} — {nc}"
                    data.articles[art_name] = {
                        "history": pd.Series(series.values, name=art_name),
                        "forecast_erp": pd.Series(dtype=float),
                    }
    return data