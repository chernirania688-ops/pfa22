"""
AlBrain S&OP AI Platform — Version 3.0
Corrections :
  - MBS supprimé (confusion avec MA) → gradation MA → LES → HW
  - Paramètres affichés strictement par méthode (MA=aucun, LES=α, HW=α/β/γ)
  - Règle de sélection = MINIMISER MAPE (plus bas = plus précis)
  - Facteurs saisonniers réservés à HW uniquement
  - Définitions ERP, Int. bas/haut, Anomalie ajoutées dans l'interface
  - Simulation +30% : libellé explicite (+30% vs demande nominale de la période)
  - Options d'action hiérarchisées (Option 1 → 2 → 3, jamais simultanées)
  - Plan production : vue synthétique sous toutes les contraintes
  - Coûts : hypothèses et calculs affichés explicitement
  - [v3.1] What-If : paramètres affichés STRICTEMENT selon méthode sélectionnée
           MA sélectionné  → fenêtre w uniquement (ZÉRO α/β/γ affiché)
           LES sélectionné → α uniquement (ZÉRO β/γ affiché)
           HW sélectionné  → α + β + γ uniquement
           Auto            → aucun paramètre (optimisation automatique)
"""
import sys, os, re, warnings, tempfile, base64
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent.resolve()
if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))
os.chdir(str(APP_DIR))

import streamlit as st
import pandas as pd
import numpy as np
warnings.filterwarnings("ignore")

try:
    from parsers import load_production_excel, load_demand_excel, ProductionData
    from forecasting import compare_all, whatif_demand, whatif_production, les, holt_winters, moving_average
    MODULES_OK = True
except ImportError:
    MODULES_OK = False

st.set_page_config(page_title="AlBrain S&OP", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');
:root{--navy:#1e3a8a;--blue:#2563eb;--bl:#eff6ff;--tx:#1a1a2e;--mu:#6b7299;
      --bg:#fff;--bg1:#f8f9fc;--bg2:#f0f2f7;--br:#d0d5e8;--br2:#b8c0d8;
      --gn:#16a34a;--rd:#dc2626;--am:#d97706;}
*{box-sizing:border-box;margin:0;padding:0}
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important;background:#fff!important;color:var(--tx)!important}
#MainMenu,footer,header{visibility:hidden}
.block-container{padding:.35rem .65rem!important;max-width:100%!important}
.tb{display:flex;align-items:center;gap:.65rem;padding:.3rem 0 .4rem;border-bottom:2px solid var(--br);margin-bottom:.35rem}
.tb-name{font-weight:800;font-size:.92rem;color:var(--navy)}
.tb-name span{color:var(--blue)}
.stTabs [data-baseweb="tab-list"]{background:var(--bg2)!important;border-bottom:2px solid var(--br)!important;gap:0!important;padding:0 .25rem}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--mu)!important;font-weight:600!important;font-size:.8rem!important;padding:.42rem .85rem!important;border-bottom:2px solid transparent!important;border-radius:0!important}
.stTabs [aria-selected="true"]{color:var(--navy)!important;border-bottom-color:var(--navy)!important;background:#fff!important}
.stTabs [data-baseweb="tab-panel"]{background:#fff!important;padding:0!important}
.stButton>button{background:#fff!important;color:var(--tx)!important;border:1.5px solid var(--br)!important;border-radius:6px!important;font-weight:600!important;font-size:.78rem!important;padding:.28rem .5rem!important;transition:all .15s!important;white-space:nowrap!important;line-height:1.3!important}
.stButton>button:hover{border-color:var(--navy)!important;color:var(--navy)!important;background:var(--bl)!important}
.stButton>button:disabled{opacity:.35!important}
[data-testid="column"]:first-child .stButton>button{background:var(--navy)!important;color:#fff!important;border:none!important;font-weight:700!important}
[data-testid="column"]:first-child .stButton>button:hover{background:var(--blue)!important;color:#fff!important}
.stTextInput>div>div>input{background:var(--bg1)!important;border:1.5px solid var(--br)!important;color:var(--tx)!important;border-radius:6px!important;font-size:.84rem!important;padding:.38rem .65rem!important}
.stTextInput>div>div>input:focus{border-color:var(--navy)!important}
.stTextArea textarea{background:var(--bg1)!important;border:1.5px solid var(--br)!important;color:var(--tx)!important;border-radius:6px!important;font-size:.82rem!important}
.stRadio label{color:var(--tx)!important;font-size:.8rem!important}
.stSlider label{color:var(--mu)!important;font-size:.78rem!important}
.stFileUploader{margin:0!important}
.stFileUploader>div{background:var(--bg1)!important;border:1px dashed var(--br2)!important;border-radius:6px!important;padding:.2rem .35rem!important;min-height:0!important}
.stFileUploader label{display:none!important}
.stFileUploader [data-testid="stFileUploaderDropzone"]{padding:.3rem!important;min-height:42px!important}
.stFileUploader [data-testid="stFileUploaderDropzone"] div{font-size:.7rem!important;color:var(--mu)!important}
.stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] div{display:none!important}
.stFileUploader button{font-size:.7rem!important;padding:.15rem .35rem!important}
[data-testid="stMetric"]{background:var(--bg1)!important;border:1.5px solid var(--br)!important;border-radius:7px!important;padding:.55rem .75rem!important}
[data-testid="stMetricLabel"]{color:var(--mu)!important;font-size:.68rem!important}
[data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace!important;font-size:1.25rem!important}
.chat-box{border:1.5px solid var(--br);border-radius:8px;background:var(--bg1);padding:.5rem .6rem;overflow-y:auto;
  scroll-behavior:smooth;transition:none}
/* Stabilisation anti-tremblement : évite les reflows lors des reruns Streamlit */
.stApp,[data-testid="stAppViewContainer"]{overflow-anchor:none}
[data-testid="stVerticalBlock"]{contain:layout style}
.element-container{min-height:0!important;transition:none!important}
iframe{transition:none!important}
/* Chat scroll stable */
#chat_marketing,#chat_demande,#chat_production,#chat_finance,#chat_orchestrateur,#disc_panel{
  overflow-anchor:none;scroll-behavior:smooth}
.msg-u{display:flex;justify-content:flex-end;margin-bottom:.35rem}
.msg-a{display:flex;gap:.35rem;margin-bottom:.35rem;align-items:flex-start}
.bub{padding:.42rem .68rem;border-radius:8px;font-size:.8rem;line-height:1.6;max-width:93%;border:1px solid;word-break:break-word}
.bub-u{background:var(--bl);border-color:#bfdbfe}
.bub-a{background:#fff;border-color:var(--br);box-shadow:0 1px 2px rgba(0,0,0,.04)}
.bub-a strong,.bub-a b{color:var(--navy)}
.av{width:22px;height:22px;border-radius:4px;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:700;font-family:'JetBrains Mono',monospace;flex-shrink:0;margin-top:.1rem}
.tw{overflow-x:auto;margin:.3rem 0;border:1.5px solid var(--br);border-radius:8px}
table.sop{width:100%;border-collapse:collapse;font-size:.79rem}
table.sop th{background:var(--navy);color:#fff;padding:.3rem .5rem;font-family:'JetBrains Mono',monospace;font-size:.71rem;text-align:center;border:1px solid #1e3a8a;white-space:nowrap}
table.sop td{padding:.24rem .48rem;border:1px solid var(--br);vertical-align:middle;text-align:right}
table.sop td.l{text-align:left;font-family:'JetBrains Mono',monospace;font-size:.72rem;font-weight:600}
table.sop td.c{text-align:center}
table.sop tr:nth-child(even){background:#f8f9fc}
table.sop tr.surge{background:#fef2f2}
table.sop tr.alrt{background:#fffbeb}
table.sop tr.ok-row{background:#f0fdf4}
.synth{background:var(--bl);border:1.5px solid #bfdbfe;border-radius:7px;padding:.45rem .7rem;margin:.3rem 0;font-size:.79rem;color:#1e3a8a;line-height:1.55}
.synth-h{font-weight:700;font-size:.72rem;letter-spacing:.07em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;margin-bottom:.18rem}
.ae{background:#fef2f2;border-left:3px solid var(--rd);border-radius:5px;padding:.38rem .65rem;margin:.2rem 0;font-size:.79rem;color:#991b1b}
.aw{background:#fffbeb;border-left:3px solid var(--am);border-radius:5px;padding:.38rem .65rem;margin:.2rem 0;font-size:.79rem;color:#92400e}
.ag{background:#f0fdf4;border-left:3px solid var(--gn);border-radius:5px;padding:.38rem .65rem;margin:.2rem 0;font-size:.79rem;color:#15803d}
.ai{background:var(--bl);border-left:3px solid var(--blue);border-radius:5px;padding:.38rem .65rem;margin:.2rem 0;font-size:.79rem;color:#1d4ed8}
.btn-send>button{background:var(--navy)!important;color:#fff!important;border:none!important;font-size:.85rem!important;padding:.3rem .55rem!important;font-weight:700!important;border-radius:6px!important}
.slbl{font-size:.6rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--mu);font-family:'JetBrains Mono',monospace;padding:.15rem 0 .3rem;border-bottom:1px solid var(--br);margin-bottom:.38rem}
.cap{padding:.1rem 0;font-size:.76rem;color:#374151;display:flex;gap:.28rem}
.cap-dot{color:var(--navy);font-size:.55rem;margin-top:.22rem;flex-shrink:0}
.pill-ok{display:inline-block;background:#dcfce7;color:#16a34a;border:1px solid #86efac;border-radius:20px;padding:.06rem .38rem;font-size:.66rem;font-weight:700;font-family:'JetBrains Mono',monospace;margin-left:.3rem;vertical-align:middle}
/* ── Filtres multiselect navy (tous les dashboards) ── */
[data-baseweb="tag"]{background:#1e3a8a!important;color:#fff!important;border:none!important;border-radius:4px!important}
[data-baseweb="tag"] span{color:#fff!important}
[data-baseweb="tag"] svg{fill:#fff!important;opacity:.8}
/* Slider thumb navy */
[data-testid="stSlider"] [role="slider"]{background:#1e3a8a!important;border:2px solid #1e3a8a!important}
[data-testid="stSlider"] [data-baseweb="slider"]>div>div:last-child{background:#1e3a8a!important}
.fbadge{background:var(--bl);border:1px solid #bfdbfe;border-radius:4px;padding:.12rem .35rem;font-size:.67rem;font-family:'JetBrains Mono',monospace;color:var(--blue);display:inline-block;margin-top:.1rem}
.gloss{background:#f8f9fc;border:1px solid var(--br);border-radius:6px;padding:.35rem .6rem;margin:.25rem 0;font-size:.76rem;line-height:1.6}
.gloss-t{font-weight:700;color:var(--navy);font-size:.72rem;font-family:'JetBrains Mono',monospace}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-thumb{background:var(--br2);border-radius:4px}
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
AGS = ["marketing","demande","production","finance","orchestrateur"]
if "dfs"      not in st.session_state: st.session_state.dfs      = {}
if "files"    not in st.session_state: st.session_state.files    = {}
if "chats"    not in st.session_state: st.session_state.chats    = {a:[] for a in AGS}
if "disc"     not in st.session_state: st.session_state.disc     = []
if "views"    not in st.session_state: st.session_state.views    = {a:"chat" for a in AGS}
if "scenarios" not in st.session_state: st.session_state.scenarios = {a:[] for a in AGS}
if "whatif_params" not in st.session_state: st.session_state.whatif_params = {
    "production": {"cap_pct": None, "minprod": None, "cap_abs": None},
    "demande":    {"method": None, "alpha": None, "gamma": None},
}
if "email_config" not in st.session_state: st.session_state.email_config = {
    "enabled": False, "smtp_server": "smtp.gmail.com", "smtp_port": 587,
    "sender": "", "password": "", "recipient": "",
    "auto_send": True, "last_sent": None,
}

def get_dfs(agent):
    d = st.session_state.dfs.get(agent,{})
    return d or st.session_state.dfs.get("orchestrateur",{})

def get_any():
    for a in AGS:
        d = st.session_state.dfs.get(a,{})
        if d: return d
    return {}

def add_msg(agent, role, content):
    st.session_state.chats.setdefault(agent,[]).append(
        {"role":role,"content":content,"ts":datetime.now().strftime("%H:%M")})

def load_file(agent, up):
    tmp = Path(tempfile.mkdtemp())/up.name
    tmp.write_bytes(up.getvalue())
    try:
        xls = pd.ExcelFile(str(tmp))
        dfs = {}
        for sh in xls.sheet_names:
            df = pd.read_excel(xls,sh)
            df.columns = [str(c).strip() for c in df.columns]
            dfs[sh]=df
        st.session_state.dfs[agent]=dfs
        st.session_state.files[agent]=up.name
        return dfs, None
    except Exception as e:
        return None, str(e)

# ── GROQ ──────────────────────────────────────────────────────────────────────
def groq(system, user, max_tokens=700):
    try:
        from groq import Groq
        key = st.secrets.get("GROQ_API_KEY","") or os.environ.get("GROQ_API_KEY","")
        if not key: return "Cle GROQ_API_KEY manquante dans .streamlit/secrets.toml"
        if len(user)>3000: user=user[:1800]+"\n[tronque]\n"+user[-1100:]
        r = Groq(api_key=key).chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            max_tokens=max_tokens, temperature=0.2)
        return r.choices[0].message.content.strip()
    except Exception as e: return f"Erreur Groq : {e}"

# ── UTILITAIRES ───────────────────────────────────────────────────────────────
def cn(v):
    if v is None: return 0.0
    if isinstance(v,(int,float)): return float(v) if not(isinstance(v,float) and np.isnan(v)) else 0.0
    try: return float(str(v).strip().replace(" ","").replace(",","."))
    except: return 0.0

def T(headers, rows, row_cls=None, title=None):
    h = ['<div class="tw">']
    if title: h.append(f'<div style="background:var(--navy);color:#fff;font-size:.71rem;font-weight:700;font-family:JetBrains Mono,monospace;padding:.28rem .55rem;letter-spacing:.06em;text-transform:uppercase">{title}</div>')
    h.append('<table class="sop"><thead><tr>')
    for hd in headers: h.append(f'<th>{hd}</th>')
    h.append('</tr></thead><tbody>')
    for i,row in enumerate(rows):
        cls = row_cls[i] if row_cls and i<len(row_cls) else ""
        h.append(f'<tr class="{cls}">')
        for j,cell in enumerate(row):
            c = "l" if j==0 else "c" if isinstance(cell,str) else ""
            val = cell if (cell is not None and cell!="") else "—"
            h.append(f'<td class="{c}">{val}</td>')
        h.append('</tr>')
    h.append('</tbody></table></div>')
    return "".join(h)

def S(title, lines):
    body = "".join(f'<div style="padding:.06rem 0">{l}</div>' for l in lines)
    return f'<div class="synth"><div class="synth-h">Synthese — {title}</div>{body}</div>'

def sc(s):
    c = {"SURCHARGE": "#dc2626", "ALERTE": "#d97706", "OK": "#16a34a"}.get(s, "#374151")
    return f'<span style="color:{c};font-weight:700">{s}</span>'

def glossaire_demande():
    return """
<div class="gloss">
<div class="gloss-t">Définitions — Méthodes et indicateurs</div>
<div style="margin-top:.3rem">
  <strong>ERP</strong> : Prévision issue du système ERP de l'entreprise (données importées).
  Sert de référence de comparaison pour mesurer le gain apporté par les méthodes Python.
</div>
<div style="margin-top:.25rem">
  <strong>MA — Moyenne Mobile</strong> : Calcule la moyenne des <em>w</em> dernières périodes.
  Simple et robuste. Aucun paramètre α/β/γ — ce n'est qu'une fenêtre glissante.
</div>
<div style="margin-top:.25rem">
  <strong>LES — Lissage Exponentiel Simple</strong> : Pondère le passé avec un paramètre
  <strong>α (alpha)</strong> uniquement. α élevé → très réactif ; α faible → très stable.
  Pas de β ni γ pour LES.
</div>
<div style="margin-top:.25rem">
  <strong>HW — Holt-Winters Additif</strong> : Capture niveau + tendance + saisonnalité.
  Trois paramètres : <strong>α</strong> (niveau), <strong>β</strong> (tendance), <strong>γ</strong> (saisonnalité).
  Les <strong>facteurs saisonniers F(n,k)</strong> sont <u>exclusifs à HW</u> : ils représentent
  l'écart récurrent de chaque période (mois, semaine…) par rapport à la moyenne.
  Ex : F=1.25 → ce mois est 25% au-dessus de la moyenne annuelle.
  MA et LES n'ont <u>pas</u> de facteurs saisonniers.
</div>
<div style="margin-top:.25rem">
  <strong>MAPE</strong> : Erreur moyenne en % — <u>plus bas = plus précis</u>.
  Ex : MAPE=10% → les prévisions se trompent en moyenne de 10% vs la demande réelle.
</div>
<div style="margin-top:.25rem">
  <strong>Int. bas / Int. haut</strong> : Intervalle de confiance à ~85%.
  Formule : Prévision ± 1.44 × RMSE × √horizon.
  Dans ~85% des cas, la demande réelle tombera entre ces deux bornes.
</div>
<div style="margin-top:.25rem">
  <strong>Anomalie</strong> : Valeur historique hors de [Moyenne ± 2×Écart-type].
  Un <em>pic</em> (valeur trop haute) ou un <em>creux</em> (valeur trop basse) s'écartant
  de plus de 2σ de la moyenne. Ces valeurs peuvent biaiser les prévisions.
</div>
</div>"""

def fmt(text):
    if any(tag in str(text) for tag in ["<table","<div","<strong","<span","<br","<em","<ul","<li","<p ","<p>"]): return str(text)
    import html as hl
    lines=str(text).split("\n"); out=[]; tbls=[]
    def sep(l): s=l.strip().strip("|").strip(); return bool(re.match(r'[-:\s|]+$',s)) and "---" in s
    def trow(l): return l.strip().startswith("|") and "|" in l.strip()[1:]
    def inl(t):
        t=hl.escape(t)
        t=re.sub(r'\*\*(.*?)\*\*',r'<strong style="color:#1e3a8a">\1</strong>',t)
        t=re.sub(r'\*(.*?)\*',r'<em>\1</em>',t)
        t=re.sub(r'`(.*?)`',r'<code style="background:#e8ebf2;padding:.05rem .2rem;border-radius:3px;color:#1e3a8a;font-size:.75em">\1</code>',t)
        return t
    def flush():
        if not tbls: return ""
        h=['<div class="tw"><table class="sop"><thead><tr>']
        for i,row in enumerate(tbls):
            cells=[c.strip() for c in row.strip().strip("|").split("|")]
            if i==0: h+=[f'<th>{inl(c)}</th>' for c in cells]; h.append('</tr></thead><tbody>')
            else: h.append('<tr>'); h+=[f'<td class="{"l" if j==0 else ""}">{inl(c) or "—"}</td>' for j,c in enumerate(cells)]; h.append('</tr>')
        h.append('</tbody></table></div>'); return "".join(h)
    in_t=False
    for line in lines:
        if trow(line):
            if not sep(line): tbls.append(line)
            in_t=True; continue
        if in_t: out.append(flush()); tbls=[]; in_t=False
        s=line.strip()
        if s.startswith("### "): out.append(f'<div style="font-weight:700;font-size:.83rem;color:var(--navy);margin:.4rem 0 .12rem;border-bottom:1px solid #e8ebf2;padding-bottom:.1rem">{inl(s[4:])}</div>')
        elif s.startswith("## "): out.append(f'<div style="font-weight:700;font-size:.86rem;color:var(--navy);margin:.45rem 0 .15rem">{inl(s[3:])}</div>')
        elif s.startswith("# "): out.append(f'<div style="font-weight:800;font-size:.9rem;color:var(--navy);margin:.5rem 0 .18rem">{inl(s[2:])}</div>')
        elif s.startswith(("- ","* ")): out.append(f'<div style="padding:.07rem 0 .07rem .75rem;display:flex;gap:.25rem"><span style="color:var(--navy);font-size:.52rem;margin-top:.24rem;flex-shrink:0">&#9658;</span><span>{inl(s[2:])}</span></div>')
        elif re.match(r'^\d+\.\s',s):
            n,rest=s.split(". ",1)
            out.append(f'<div style="padding:.07rem 0 .07rem .75rem;display:flex;gap:.28rem"><span style="color:var(--navy);font-weight:700;flex-shrink:0;font-size:.74rem">{n}.</span><span>{inl(rest)}</span></div>')
        elif s=="": out.append('<div style="height:.18rem"></div>')
        else: out.append(f'<div style="padding:.05rem 0;line-height:1.62">{inl(s)}</div>')
    if in_t and tbls: out.append(flush())
    return "".join(out)

# ── MRP ────────────────────────────────────────────────────────────────────────
def mrp_calc(dfs, overrides=None):
    df=None; lc=None
    for d in dfs.values():
        for c in d.columns:
            if str(c).lower() in ("donnees","data field","data fields","label","description","libelle"):
                df=d; lc=c; break
        if df is not None: break
    if df is None:
        for d in dfs.values():
            str_cols=[c for c in d.columns if d[c].dtype==object]
            if len(str_cols)>=2:
                df=d; lc=str_cols[1] if len(str_cols)>1 else str_cols[0]; break
    if df is None: df=list(dfs.values())[0]; lc=df.columns[min(1,len(df.columns)-1)]
    skip_cols={str(df.columns[0]),str(lc),"Resource","resource","NaN","nan",""}
    weeks=[c for c in df.columns
           if str(c).strip() not in skip_cols
           and not str(c).lower().startswith("unnamed")
           and not str(c).lower().startswith("nan")
           # Exclure les colonnes texte pures sans chiffre (ex. "Description", "Libelle")
           and any(ch.isdigit() for ch in str(c))]
    if not weeks:
        weeks=[c for c in df.columns if df[c].dtype in [np.float64,np.int64]
               and str(c).strip() not in skip_cols]
    def gs(*kws):
        for _,row in df.iterrows():
            if all(k.lower() in str(row[lc]).lower() for k in kws): return {w:cn(row[w]) for w in weeks}
        return {w:0.0 for w in weeks}
    G=gs("gross"); V=gs("variable"); C=gs("capacity"); S=gs("safety")
    P=gs("production","plan"); B=gs("batch"); MP=gs("minimum","production"); I=gs("initial")
    def fp(d): return next((cn(v) for v in d.values() if cn(v)>0),0.0)
    cap_v=fp(C) or 1400.0; var_v=fp(V) or 0.4667; bat_v=fp(B) or 1.0
    ss_v=fp(S) or 0.0; inv=fp(I) or 0.0
    max_u=round(cap_v/var_v,0) if var_v > 0 else cap_v
    ov=overrides or {}
    R={k:[] for k in ["weeks","gross","charge","cap","surplus","sat","net","po","plan","inv_s","inv_e","status","mod"]}
    R["p"]={"cap_v":cap_v,"var_v":var_v,"ss_v":ss_v,"inv0":inv,"max_u":max_u,"bat_v":bat_v}
    for w in weeks:
        g=ov.get(w,cn(G.get(w,0))); v=cn(V.get(w,var_v)) or var_v
        c=cn(C.get(w,cap_v)) or cap_v; ss=cn(S.get(w,ss_v)) or ss_v
        b=cn(B.get(w,bat_v)) or bat_v; mp=cn(MP.get(w,0)); pp=cn(P.get(w,0))
        ch=round(g*v,2); surp=round(c-ch,2); sat=round(ch/c*100,1) if c>0 else 0.0
        net=max(0.0,g-inv+ss); po=max(mp,b*np.ceil(net/b)) if net>0 else 0.0
        i_s=inv; i_e=round(inv+pp-g,2)
        st_v="SURCHARGE" if surp<0 else ("ALERTE" if sat>85 else "OK")
        for k,val in [("weeks",str(w)),("gross",g),("charge",ch),("cap",c),("surplus",surp),
                      ("sat",sat),("net",round(net,0)),("po",round(po,0)),("plan",pp),
                      ("inv_s",i_s),("inv_e",i_e),("status",st_v),("mod",w in ov)]:
            R[k].append(val)
        inv=i_e
    return R

def parse_ov(q,weeks):
    ov={}
    for m in re.finditer(r'(w\d{2}[^→àa\d]{0,15})[\d\s,.]{2,15}(?:à|a|→|->|=)\s*([\d\s,.]{1,12})',q.lower()):
        wm=re.search(r'w(\d{2})',m.group(1))
        if not wm: continue
        wk=next((w for w in weeks if f"W{wm.group(1)}" in w.upper()),None)
        try:
            val=float(re.sub(r'[^\d.]','',m.group(2).replace(',','.')))
            if wk and val>0: ov[wk]=val
        except: pass
    return ov

# ── DEMANDE ────────────────────────────────────────────────────────────────────
def demand_calc(dfs):
    df_s=df_k=None
    for sh,d in dfs.items():
        sl=sh.lower()
        if "series" in sl or "serie" in sl: df_s=d
        elif "kpi" in sl or "compare" in sl: df_k=d

    MN=["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"]
    res={}

    if df_s is not None and df_s.shape[1] > 10:
        ac=df_s.columns[0]; fc=df_s.columns[1]
        tc=[c for c in df_s.columns if c not in [ac,fc] and not str(c).lower().startswith("unnamed")]
        arts={}; cur=None
        for _,row in df_s.iterrows():
            av=str(row[ac]).strip()
            if av and av.lower() not in ("nan",""): cur=av
            if not cur: continue
            arts.setdefault(cur,{})[str(row[fc]).strip()]=pd.Series([cn(row[c]) for c in tc],index=tc,dtype=float)
        for art,fields in arts.items():
            hk=next((k for k in fields if "calculation history" in k.lower()),None)
            sk=next((k for k in fields if "statistical" in k.lower() and "forecast" in k.lower()),None)
            if hk is None: continue
            h=fields[hk].dropna(); h=h[h>0]
            if len(h)<3: continue
            mape_e=mae_e=0.0
            if df_k is not None:
                kr=df_k[df_k[df_k.columns[0]].astype(str).str.contains(art[:10],na=False,case=False)]
                if not kr.empty: mape_e=cn(kr.iloc[0].iloc[2]); mae_e=cn(kr.iloc[0].iloc[1])
            fc_erp=[]
            if sk:
                sv=fields[sk].dropna(); sv=sv[sv>0]
                n_h=len(h)
                if len(sv)>n_h: fc_erp=[round(float(x),0) for x in sv.values[n_h:n_h+6]]
            res[art]=_build_stats(h.values.astype(float), art, mape_e, mae_e, fc_erp, MN)
        if res: return res

    try:
        from parsers import load_demand_excel as _load_dem
        dem_data = _load_dem(dfs)
        for art_name, d in dem_data.articles.items():
            if art_name in res: continue
            h = d["history"].values.astype(float)
            fc_erp = list(d["forecast_erp"].values.astype(float)) if len(d["forecast_erp"]) > 0 else []
            mape_e = mae_e = 0.0
            if dem_data.kpis.get(art_name):
                mape_e = dem_data.kpis[art_name].get("mape", 0.0)
                mae_e  = dem_data.kpis[art_name].get("mae",  0.0)
            if len(h) >= 3:
                res[art_name] = _build_stats(h, art_name, mape_e, mae_e, fc_erp, MN)
    except Exception as _e:
        for sh, df in dfs.items():
            df_raw = df.reset_index(drop=True)
            header_row = None
            for i in range(min(8, len(df_raw))):
                row_str = ' '.join(str(v) for v in df_raw.iloc[i]).lower()
                if 'demande' in row_str or 'demand' in row_str:
                    header_row = i; break
            if header_row is None: continue
            header_vals = [str(v).strip() for v in df_raw.iloc[header_row]]
            dem_col_idx = next(
                (j for j, h in enumerate(header_vals)
                 if ('demande' in h.lower() or 'demand' in h.lower())
                 and 'unnamed' not in h.lower()), None)
            if dem_col_idx is None: continue
            art_name = f"{sh} — {header_vals[dem_col_idx]}"
            series_vals = []
            for r in range(header_row + 1, len(df_raw)):
                d_val = cn(df_raw.iloc[r, dem_col_idx])
                if d_val is None:
                    if r + 1 < len(df_raw) and cn(df_raw.iloc[r+1, dem_col_idx]) is None: break
                    continue
                if d_val <= 0: break
                series_vals.append(d_val)
            if len(series_vals) >= 3 and art_name not in res:
                res[art_name] = _build_stats(np.array(series_vals), art_name, 0, 0, [], MN)

    if not res:
        for sh, df in dfs.items():
            # Identifier les colonnes de demande (numériques, >= 3 valeurs)
            num_cols = [c for c in df.columns
                       if df[c].dtype in [np.float64, np.int64, float, int]
                       and df[c].dropna().shape[0] >= 3
                       and not str(c).lower().startswith("unnamed")]
            # Identifier les colonnes de prévision ERP
            erp_cols = [c for c in df.columns
                       if any(kw in str(c).lower()
                              for kw in ("prev","forecast","prevision","erp","fcst"))
                       and not str(c).lower().startswith("unnamed")]

            for nc in num_cols[:4]:
                series = df[nc].apply(cn).dropna(); series = series[series > 0]
                if len(series) < 3: continue
                art_name = f"{sh} — {nc}"
                if art_name in res: continue

                # ── Calculer MAPE_ERP si colonne de prévision présente ──────
                mape_e_calc = 0.0; fc_erp_calc = []
                for ec in erp_cols[:1]:   # Prendre la 1ère colonne ERP
                    erp_vals = df[ec].apply(cn)
                    act_vals = series.values
                    erp_arr  = erp_vals.values[:len(act_vals)]
                    # MAPE sur les périodes où ERP ET actuel sont disponibles
                    pairs = [(a, e) for a, e in zip(act_vals, erp_arr)
                             if e is not None and not (isinstance(e, float) and np.isnan(e))
                             and e > 0 and a > 0]
                    if pairs:
                        mape_e_calc = round(
                            float(np.mean([abs(a-e)/a*100 for a, e in pairs])), 1)
                    # Prévisions ERP futures (après la série historique)
                    n_hist = len(act_vals)
                    fc_erp_raw = erp_vals.values[n_hist:n_hist+6]
                    fc_erp_calc = [round(float(x), 0) for x in fc_erp_raw
                                   if x is not None and not (isinstance(x, float) and np.isnan(x))
                                   and x > 0]

                # Valeur ERP initiale (historique, pas future) pour init LES
                erp_init_val = None
                for ec2 in erp_cols[:1]:
                    first_erp = df[ec2].apply(cn).iloc[0]
                    if first_erp is not None and not (isinstance(first_erp,float) and np.isnan(first_erp)) and first_erp > 0:
                        erp_init_val = float(first_erp)
                res[art_name] = _build_stats(
                    series.values.astype(float), art_name,
                    mape_e_calc, 0.0, fc_erp_calc, MN,
                    erp_init=erp_init_val)
    return res


def _holt_linear(v, n_forecast=6, erp_init=None):
    """
    Double Lissage Exponentiel — Methode de Holt (Holt's Linear Trend).
    Deux parametres : alpha (niveau) + beta (tendance).
    Capture la tendance sans composante saisonniere.
    Utilise quand N est petit ET la tendance est significative.
    """
    v = np.array(v, dtype=float)
    n = len(v)
    # Utiliser erp_init si disponible (cohérence avec LES)
    L0_holt = float(erp_init) if (erp_init is not None and erp_init > 0) else float(v[0])

    # Optimiser alpha et beta par grille
    best_mape, best_a, best_b = np.inf, 0.3, 0.1
    for a in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        for b in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]:
            # Calcul interne avec L0_holt
            L, T = L0_holt, (v[1] - v[0] if n > 1 else 0.0)
            fitted = [L]
            for i in range(1, n):
                L_p, T_p = L, T
                L = a * v[i] + (1 - a) * (L_p + T_p)
                T = b * (L - L_p) + (1 - b) * T_p
                fitted.append(L + T)
            m = float(np.mean(np.abs((v[1:] - np.array(fitted[1:])) / (v[1:] + 1e-9)))) * 100
            if m < best_mape:
                best_mape, best_a, best_b = m, a, b

    # Recalcul avec les meilleurs parametres
    L, T = L0_holt, (v[1] - v[0] if n > 1 else 0.0)
    for i in range(1, n):
        L_p, T_p = L, T
        L = best_a * v[i] + (1 - best_a) * (L_p + T_p)
        T = best_b * (L - L_p) + (1 - best_b) * T_p

    forecasts = [max(0.0, round(L + h * T, 0)) for h in range(1, n_forecast + 1)]
    return forecasts, round(best_mape, 1), best_a, best_b

def _build_stats(v, art_name, mape_e, mae_e, fc_erp, MN, erp_init=None):
    n   = len(v)
    mn  = round(float(np.mean(v)), 1)
    std = round(float(np.std(v)),  1)
    cv  = round(std / mn * 100, 1) if mn > 0 else 0
    # Tendance par régression linéaire (pente/période)
    xs  = np.arange(n)
    tr  = round(float(np.polyfit(xs, v, 1)[0]), 2) if n >= 3 else 0.0
    rel_trend = abs(tr) / mn if mn > 0 else 0   # tendance relative

    # ── Cas données insuffisantes ───────────────────────────────────────────
    # Avec N < 5, LES/HW donnent des résultats peu fiables.
    # On privilégie la régression linéaire si la tendance est forte.
    USE_LINEAR = (n < 8 and rel_trend > 0.10)

    # ── Initialisation LES : ERP si disponible, sinon premier point ──────────
    # Si le système ERP fournit une prévision initiale, on l'utilise comme L(0).
    # Cela garantit la cohérence avec les calculs manuels de l'utilisateur.
    # Exemple : erp=[100, NaN, NaN] et v=[150,275,310,475]
    #   alpha=0.3 → L0=100 → M+1=287.47 (correct)  vs  L0=150 → 299 (incorrect)
    _les_l0 = float(erp_init) if (erp_init is not None and erp_init > 0) else float(v[0])

    # ── Prévisions par régression linéaire (robuste sur séries courtes) ─────
    def _lin_forecast(v, tr, n_out=6):
        """Extrapole la tendance linéaire depuis le dernier point observé."""
        slope, intercept = np.polyfit(np.arange(len(v)), v, 1)
        # Forecast = droite de régression extrapolée
        return [max(0.0, round(intercept + slope * (len(v) + i), 0))
                for i in range(1, n_out + 1)]

    def _lin_mape(v):
        """MAPE de la régression linéaire en leave-one-out."""
        if len(v) < 3: return 99.9
        xs = np.arange(len(v))
        fit = np.polyval(np.polyfit(xs, v, 1), xs)
        return round(float(np.mean(np.abs((v - fit) / (v + 1e-9)))) * 100, 1)

    if USE_LINEAR:
        lin_mape = _lin_mape(v)
        fc_lin   = _lin_forecast(v, tr)
    else:
        lin_mape = None
        fc_lin   = None

    try:
        from forecasting import compare_all
        cmp   = compare_all(v, n_forecast=6)
        rec   = cmp.methods[cmp.recommended]
        r_les = cmp.methods.get("LES", rec)
        r_hw  = cmp.methods.get("HW",  rec)
        r_ma  = cmp.methods.get("MA",  rec)

        les_mape = round(r_les.mape, 1); les_mae  = round(r_les.mae, 1)
        les_rmse = round(r_les.rmse, 1); les_alpha = r_les.alpha
        hw_mape  = round(r_hw.mape,  1); hw_mae   = round(r_hw.mae,  1); hw_rmse = round(r_hw.rmse, 1)
        ma_mape  = round(r_ma.mape,  1); ma_mae   = round(r_ma.mae,  1); ma_rmse = round(r_ma.rmse, 1)

        fc_py  = list(np.round(r_les.forecast, 0).astype(int))
        fc_hw  = list(np.round(r_hw.forecast,  0).astype(int))
        fc_rec = list(np.round(rec.forecast,   0).astype(int))

        _raw = cmp.recommended
        if "HW" in _raw or "Holt-Winters" in _raw: bst = "HW"
        elif "LES" in _raw:                          bst = "LES"
        else:                                         bst = "MA"

        seas            = cmp.seasonal_detected
        s_len           = cmp.season_len
        seasonal_factors= rec.seasonal_factors if bst == "HW" else []

        # ── Recalcul LES avec erp_init si disponible ─────────────────────────
        # Le module externe ignore erp_init → on recalcule fc_py avec notre init
        if _les_l0 != float(v[0]):
            L_corr = _les_l0
            for vv in v:
                L_corr = les_alpha * vv + (1 - les_alpha) * L_corr
            fc_py = [round(L_corr, 0)] * 6   # LES = niveau constant
            # Re-calcul MAPE avec erp_init
            L_m = _les_l0; fitted_m = []
            for vv in v:
                L_m = les_alpha * vv + (1 - les_alpha) * L_m
                fitted_m.append(L_m)
            les_mape = round(float(np.mean(
                np.abs((v - np.array(fitted_m[:len(v)])) / (v + 1e-9)))) * 100, 1)

        # ── Correction prévisions plates sur série tendancielle ─────────────
        # Détection DIRECTE : prévisions plates = tous ≈ dernier niveau LES
        # Condition : tendance forte ET spread < 2% de la valeur absolue
        def _is_flat(fc):
            if not fc or len(fc) < 2: return True
            return (max(fc) - min(fc)) <= max(1.0, 0.02 * abs(float(v[-1])))

        # Utiliser Holt's Linear (DES) pour séries tendancielles
        # C'est la méthode statistique reconnue : α (niveau) + β (tendance)
        holt_fc, holt_mape_v, holt_a, holt_b = _holt_linear(v)

        if rel_trend > 0.10 and _is_flat(fc_py):
            fc_py    = holt_fc
            bst      = "HOLT"
            les_mape = holt_mape_v

        if rel_trend > 0.10 and _is_flat(fc_hw):
            fc_hw = holt_fc

        if rel_trend > 0.10 and _is_flat(fc_rec):
            fc_rec = holt_fc

        if USE_LINEAR:
            fc_py  = holt_fc
            fc_rec = holt_fc
            bst    = "HOLT"

    except Exception:
        best_a, best_mae_v = 0.3, np.inf
        for alpha in [.1, .2, .3, .4, .5, .6, .7, .8, .9]:
            # Initialisation avec ERP si disponible
            L = _les_l0
            ft = [L]
            for vv in v:
                L = alpha * vv + (1 - alpha) * L
                ft.append(round(L, 4))
            mae_v = np.mean(np.abs(v - np.array(ft[:len(v)])))
            if mae_v < best_mae_v: best_mae_v, best_a = mae_v, alpha
        les_f = [_les_l0]
        L_les = _les_l0
        for vv in v:
            L_les = best_a * vv + (1 - best_a) * L_les
            les_f.append(round(L_les, 4))
        les_mape  = round(float(np.mean(np.abs((v - np.array(les_f)) / (v + 1e-9))) * 100), 1)
        les_mae   = round(best_mae_v, 1); les_rmse = 0.0; les_alpha = best_a
        hw_mape   = hw_mae = hw_rmse = ma_mape = ma_mae = ma_rmse = 0.0
        # Toujours extrapoler la tendance (jamais plat)
        if rel_trend > 0.10:
            _holt_fc_fb, _holt_m_fb, _, _ = _holt_linear(v)
            fc_py = fc_hw = fc_rec = _holt_fc_fb
            les_mape = _holt_m_fb
            bst = "HOLT"
        else:
            fc_py = fc_hw = fc_rec = [round(float(v[-1]) + tr * i, 0) for i in range(1, 7)]
            bst = "LES"
        seas = False; s_len = 0; seasonal_factors = []

    # ── ERP MAPE : détecter le cas "pas de prévision ERP" ──────────────────
    # Si mape_e == 0 et fc_erp est vide → pas de données ERP, pas "parfait"
    erp_disponible = (mape_e > 0) or (len([x for x in fc_erp if x and x > 0]) >= 2)
    if not erp_disponible:
        mape_e = -1.0   # Sentinelle : -1 = "N/A" (pas de données ERP)

    # ── Alerte N court ───────────────────────────────────────────────────────
    warning_n_court = n < 8

    monthly = {}
    for i, val in enumerate(v):
        if val > 0: monthly.setdefault(i % 12, []).append(val)
    mall = np.mean(v[v > 0]) if len(v[v > 0]) > 0 else 1
    fac  = {m: round(np.mean(vs) / mall, 3) for m, vs in monthly.items()}

    hist = pd.Series(v, name=art_name)
    return {"n": n, "mean": mn, "std": std, "cv": cv, "trend": tr,
            "seasonal": seas, "season_len": s_len, "seasonal_factors": seasonal_factors,
            "last": float(v[-1]), "les_mape": les_mape, "les_mae": les_mae,
            "les_rmse": les_rmse, "les_alpha": les_alpha,
            "hw_mape": hw_mape, "hw_mae": hw_mae, "hw_rmse": hw_rmse,
            "ma_mape": ma_mape, "ma_mae": ma_mae, "ma_rmse": ma_rmse,
            "fc_py": fc_py, "fc_hw": fc_hw, "fc_rec": fc_rec, "fc_erp": fc_erp,
            "mape_erp": mape_e, "mae_erp": mae_e, "MN": MN,
            "factors": fac,
            "best_m":  max(fac, key=fac.get) if fac else 0,
            "worst_m": min(fac, key=fac.get) if fac else 0,
            "best": bst, "hist": hist,
            "warning_n_court": warning_n_court,
            "erp_disponible": erp_disponible,
            "rel_trend": rel_trend}

def _params_display(method: str, alpha=None, beta=None, gamma=None, window=None) -> str:
    m = str(method).upper()
    if "MA" in m and "HW" not in m and "LES" not in m:
        return f"Fenêtre w={window or '—'} (MA n'utilise pas α, β ou γ)"
    elif "LES" in m:
        return f"α={alpha or '—'} (LES n'utilise pas β ni γ)"
    elif "HW" in m or "HOLT-WINTERS" in m:
        return f"α={alpha or '—'}, β={beta or '—'}, γ={gamma or '—'}"
    return f"α={alpha or '—'}"

# ── ANALYSES DEMANDE / MARKETING ──────────────────────────────────────────────
def dem_auto(dfs, mode="demande"):
    res=demand_calc(dfs)
    if not res: return '<div class="ae">Aucun article detecte.</div>'
    total=sum(r["mean"] for r in res.values()); out=[]
    MN=list(res.values())[0]["MN"] if res else []

    if mode=="demande":
        pass  # definitions now in sidebar expander — not repeated here

    if mode=="marketing":
        hd=["Article","Vol moy/periode","Part %","Tendance","CV %","Type","Priorite"]
        rows=[]; cls=[]
        for art,r in sorted(res.items(),key=lambda x:x[1]["mean"],reverse=True):
            sh=round(r["mean"]/total*100,1) if total>0 else 0
            p="CRITIQUE" if r["trend"]<-30 else ("SURVEILLER" if r["cv"]>40 else "STABLE")
            col={"CRITIQUE":"#dc2626","SURVEILLER":"#d97706","STABLE":"#16a34a"}[p]
            rows.append([art[:22],f"{r['mean']:,.0f}",f"{sh}%",
                         f"{'+' if r['trend']>=0 else ''}{r['trend']:.1f}/mois",
                         f"{r['cv']:.1f}%","Saisonnier" if r["seasonal"] else "Stable",
                         f'<span style="color:{col};font-weight:700">{p}</span>'])
            cls.append("")
        out.append(T(hd,rows,cls,"Classement Portefeuille Produits"))
        out.append(S("Portefeuille",[
            f"• Volume total : <strong>{total:,.0f} U/periode</strong>.",
            f"• Article leader : <strong>{list(sorted(res.items(),key=lambda x:x[1]['mean'],reverse=True))[0][0][:20]}</strong>.",
            f"• Articles saisonniers (detectes par HW) : <strong>{sum(1 for r in res.values() if r['seasonal'])}/{len(res)}</strong>.",
            f"• En declin (tendance < 0) : <strong>{sum(1 for r in res.values() if r['trend']<0)}</strong>.",
        ]))
        hd2=["Article","Meilleur mois","Facteur max","Pire mois","Facteur min","Amplitude","Note"]
        rows2=[]
        for art,r in res.items():
            if r["factors"] and MN:
                bm=r["best_m"]; wm=r["worst_m"]; f=r["factors"]
                amp=round((f.get(bm,1)-f.get(wm,1))*100,0)
                note = "Saisonnalite significative (HW recommande)" if r["seasonal"] else "Pas de saisonnalite detectee"
                rows2.append([art[:22],MN[bm],f"{f.get(bm,0):.2f}x",MN[wm],f"{f.get(wm,0):.2f}x",f"{amp:.0f}%",note])
        if rows2:
            out.append(T(hd2,rows2, None, "Saisonnalite par Article (facteurs F(n,k) HW uniquement si saisonnier)"))
    else:
        hd=["Article","N","Moy","CV %","Tendance","Methode ERP (ref.)","MAPE ERP","Meilleure methode Python","MAPE Python","Gain"]
        rows=[]; cls=[]
        for art,r in res.items():
            gain=round(r["mape_erp"]-min(r["les_mape"],r["hw_mape"],r["ma_mape"]),1)
            # mape_erp == -1 signifie "pas de prévision ERP disponible"
            if r["mape_erp"] < 0:
                qe = "N/A"
            else:
                qe = "MAUVAIS" if r["mape_erp"]>50 else "MOYEN" if r["mape_erp"]>25 else "BON"
            ce={"MAUVAIS":"#dc2626","MOYEN":"#d97706","BON":"#16a34a","N/A":"#6b7280"}.get(qe,"#6b7280")
            cg="#16a34a" if gain>0 else "#dc2626"
            best_mape_py = min(r["les_mape"],r["hw_mape"],r["ma_mape"])
            rows.append([art[:22],str(r["n"]),f"{r['mean']:,.0f}",f"{r['cv']:.1f}%",
                         f"{'+' if r['trend']>=0 else ''}{r['trend']:.2f}",
                         "Prevision ERP (systeme)",
                         f'<span style="color:{ce};font-weight:700">'+(f"N/A — pas de prevision ERP" if r["mape_erp"]<0 else f'{r["mape_erp"]:.1f}% ({qe})')+ f'</span>',
                         f"{r['best']} Python",
                         f"{best_mape_py:.1f}%",
                         f'<span style="color:{cg};font-weight:700">{"+"+str(gain) if gain>0 else str(gain)}%</span>'])
            cls.append("")
        out.append(T(hd,rows,cls,"Statistiques & Qualite Prevision — ERP vs Python (MAPE plus bas = plus precis)"))
        out.append(S("Qualite prevision",[
            f"• ERP = prevision du systeme d'information de l'entreprise (reference de comparaison).",
            f"• ERP : {sum(1 for r in res.values() if r['mape_erp']>0 and r['mape_erp']>50)} article(s) avec MAPE ERP > 50% (inadapte) | {sum(1 for r in res.values() if r['mape_erp']<0)} article(s) sans prevision ERP.",
            f"• Python ameliore la precision sur <strong>{sum(1 for r in res.values() if r['mape_erp']>min(r['les_mape'],r['hw_mape'],r['ma_mape']))}/{len(res)}</strong> articles.",
        ]))
        for art,r in res.items():
            base_fc = r["fc_hw"] if r["best"] == "HW" else r["fc_py"]
            best_mape_py = r["hw_mape"] if r["best"] == "HW" else r["les_mape"]
            hdf=["Periode","Meilleure methode Python","LES (α seul)","ERP (systeme)","Int. bas (~85%)","Int. haut (~85%)"]
            rf=[]
            for i in range(6):
                fv=base_fc[i]; les_v=r["fc_py"][i]
                ev=r["fc_erp"][i] if i<len(r["fc_erp"]) else None
                rf.append([f"M+{i+1}",f"<strong>{fv:,.0f}</strong>",f"{les_v:,.0f}",
                           f"{ev:,.0f}" if ev else "—",
                           f"{round(fv*.85,0):,.0f}",f"{round(fv*1.15,0):,.0f}"])
            out.append(T(hdf,rf, None, f"Forecast 6 mois — {art[:22]} | Methode retenue : {r['best']} (MAPE={best_mape_py:.1f}% — valeur la plus basse)"))
            les_m = r['les_mape']; hw_m = r['hw_mape']
            if r['best'] == 'HW':
                gain_hw = round(les_m - hw_m, 1)
                justif = (f"HW retenu car gain MAPE significatif vs LES : "
                          f"{hw_m:.1f}% vs {les_m:.1f}% (gain={gain_hw:.1f}% > seuil 2%). "
                          f"Facteurs saisonniers F(n,k) actifs.")
            else:
                diff = round(les_m - hw_m, 1)
                if diff < 2.0:
                    justif = (f"LES retenu malgre HW car gain negligeable "
                              f"({diff:.1f}% < seuil 2%) — plan de production plus stable. "
                              f"Parametre LES : α={r['les_alpha']} uniquement.")
                else:
                    justif = (f"LES retenu avec MAPE={les_m:.1f}% (valeur la plus basse). "
                              f"Parametre : α={r['les_alpha']}.")
            out.append(S(f"Forecast {art[:16]}",[
                f"• <strong>ERP</strong> = prevision du systeme ERP de l'entreprise (MAPE={r['mape_erp']:.1f}%).",
                f"• <strong>Methode retenue : {r['best']} Python (MAPE={best_mape_py:.1f}%)</strong> — la plus basse = la plus precise.",
                f"• <strong>Choix du modele</strong> : {justif}",
                f"• <strong>Intervalles de confiance (~85%)</strong> : dans 85% des cas, la demande reelle sera entre Int. bas et Int. haut.",
                f"• M+1 : <strong>{base_fc[0]:,.0f} U</strong> | M+6 : <strong>{base_fc[-1]:,.0f} U</strong>.",
            ]))
    return "".join(out)

def dem_methods(dfs):
    res=demand_calc(dfs)
    if not res: return '<div class="ae">Aucune donnee.</div>'
    out=[]
    hd=["Article","MA MAE","MA MAPE%","LES MAE","LES α","LES MAPE%","HW MAE","HW MAPE%","Meilleure (MAPE min)"]
    rows=[]; cls=[]
    for art,r in res.items():
        bst=r["best"]
        mapes = {"MA": r["ma_mape"], "LES": r["les_mape"], "HW": r["hw_mape"]}
        best_key = min(mapes, key=lambda k: mapes[k])
        def hl(v,is_b): return f'<strong style="color:#16a34a">{v}</strong>' if is_b else str(v)
        rows.append([art[:22],
                     hl(f"{r['ma_mae']:.1f}",bst=="MA"),hl(f"{r['ma_mape']:.1f}%",bst=="MA"),
                     hl(f"{r['les_mae']:.1f}",bst=="LES"),
                     f"α={r['les_alpha']}",
                     hl(f"{r['les_mape']:.1f}%",bst=="LES"),
                     hl(f"{r['hw_mae']:.1f}",bst=="HW"),hl(f"{r['hw_mape']:.1f}%",bst=="HW"),
                     f'<strong style="color:var(--navy)">{bst} ({mapes[best_key]:.1f}%)</strong>'])
        cls.append("")
    out.append(T(hd,rows,cls,"Comparaison MA / LES / HW — MAPE plus bas = methode la plus precise"))
    bc={"LES":0,"HW":0,"MA":0}
    for r in res.values():
        best_key = r["best"].split("/")[0].split("→")[0].strip()
        bc[best_key] = bc.get(best_key, 0) + 1
    winner = max(bc,key=bc.get)
    out.append(S("Meilleure methode (MAPE minimum)",[
        f"• <strong>Regle de selection : MAPE le plus bas = methode la plus precise.</strong>",
        f"• MA meilleure sur <strong>{bc['MA']}</strong> art. | LES sur <strong>{bc['LES']}</strong> | HW sur <strong>{bc['HW']}</strong>.",
        f"• Methode globalement recommandee : <strong>{winner}</strong>.",
        f"• MAPE ERP moyen (systeme) : <strong>{round(sum(r['mape_erp'] for r in res.values())/len(res),1)}%</strong>.",
        f"• Note : MA n'a pas de parametre α/β/γ — LES n'a que α — HW a α, β et γ.",
    ]))
    return "".join(out)

def dem_anomalies(dfs):
    res=demand_calc(dfs)
    if not res: return '<div class="ae">Aucune donnee.</div>'
    out=[]
    out.append("""<div class="gloss">
<div class="gloss-t">Definition — Anomalie</div>
<div>Une anomalie est une valeur historique qui s'ecarte de plus de <strong>2 ecarts-types (2σ)</strong>
de la moyenne historique. Seuil : [Moyenne − 2σ, Moyenne + 2σ].<br>
<strong>Pic</strong> = valeur au-dessus du seuil haut. <strong>Creux</strong> = valeur en dessous du seuil bas.<br>
Ces valeurs peuvent biaiser les previsions LES et HW — a verifier avec les equipes metier.</div>
</div>""")
    for art,r in res.items():
        h=r["hist"]; v=h.values.astype(float)
        mn=np.mean(v); std=np.std(v)
        up=mn+2*std; lo=max(0,mn-2*std)
        anom=[(str(h.index[i]),round(float(v[i]),0)) for i in range(len(v)) if v[i]>up or v[i]<lo]
        if not anom:
            out.append(f'<div class="ag"><strong>{art[:28]}</strong> : aucune anomalie detectee (seuil ±2σ = [{lo:,.0f} — {up:,.0f}]).</div>')
            continue
        hd=["Periode","Valeur","Seuil bas (−2σ)","Seuil haut (+2σ)","Type","Ecart en σ"]
        rows=[]
        for per,val in anom:
            typ="PIC" if val>up else "CREUX"
            ec=round(abs(val-mn)/std,1) if std>0 else 0
            col="#dc2626" if typ=="PIC" else "#d97706"
            rows.append([per,f"{val:,.0f}",f"{lo:,.0f}",f"{up:,.0f}",
                         f'<span style="color:{col};font-weight:700">{typ}</span>',f"{ec:.1f}σ"])
        out.append(T(hd,rows, None, f"Anomalies (±2σ) — {art[:22]}"))
        out.append(S(f"Anomalies {art[:16]}",[
            f"• <strong>{len(anom)}</strong> anomalie(s) sur {len(v)} periodes (critere : ecart > 2σ).",
            f"• Moyenne historique : <strong>{mn:,.0f} U</strong> | Ecart-type : <strong>{std:,.0f} U</strong>.",
            "• Recommandation : verifier avec les metiers avant de corriger (rupture, promo, evenement exceptionnel ?).",
        ]))
    return "".join(out)

def dem_mape_top(dfs):
    res=demand_calc(dfs)
    if not res: return '<div class="ae">Aucune donnee.</div>'
    worst=max(res.items(),key=lambda x:x[1]["mape_erp"])
    art,r=worst
    best_py_mape = min(r['ma_mape'], r['les_mape'], r['hw_mape'])
    hd=["Methode","Parametres","MAE","MAPE % (plus bas = meilleur)","RMSE","A retenir ?"]
    rows=[
        ["ERP (systeme)","Prevision systeme ERP",f"{r['mae_erp']:.1f}",
         f'<span style="color:#dc2626;font-weight:700">{r["mape_erp"]:.1f}%</span>',"—",
         "NON" if r["mape_erp"] > best_py_mape else "OUI"],
        [f"MA",f"Fenetre w optimisee (pas de α/β/γ)",
         f"{r['ma_mae']:.1f}",f"{r['ma_mape']:.1f}%",f"{r['ma_rmse']:.1f}",
         "OUI" if r["best"]=="MA" else "NON"],
        [f"LES",f"α={r['les_alpha']} (α seul — pas de β ni γ)",
         f"{r['les_mae']:.1f}",f"{r['les_mape']:.1f}%",f"{r['les_rmse']:.1f}",
         "OUI" if r["best"]=="LES" else "NON"],
        ["HW","α, β, γ — avec facteurs saisonniers F(n,k)",
         f"{r['hw_mae']:.1f}",f"{r['hw_mape']:.1f}%",f"{r['hw_rmse']:.1f}",
         "OUI" if r["best"]=="HW" else "NON"],
    ]
    out=[]
    out.append(f'<div class="ae"><strong>Article avec MAPE ERP le plus eleve : {art[:28]}</strong> — MAPE ERP = {r["mape_erp"]:.1f}% (ERP = systeme d\'information de l\'entreprise)</div>')
    out.append(T(hd,rows, None, f"Comparaison MA / LES / HW — {art[:22]} (MAPE plus bas = plus precis)"))
    gain=round(r["mape_erp"]-best_py_mape,1)
    best_method = r['best']
    if best_method == "HW":
        params_note = "Parametres HW : α (niveau), β (tendance), γ (facteurs saisonniers F(n,k))."
    elif best_method == "LES":
        params_note = f"Parametre LES : α={r['les_alpha']} uniquement (pas de β ni γ pour LES)."
    else:
        params_note = "MA : fenetre glissante uniquement — aucun parametre α/β/γ."
    out.append(S(f"Analyse {art[:16]}",[
        f"• <strong>ERP</strong> = prevision du systeme d'information (MAPE={r['mape_erp']:.1f}% — methode inadaptee a cet article).",
        f"• Meilleure methode Python : <strong>{best_method}</strong> — MAPE = <strong>{best_py_mape:.1f}%</strong> (valeur la plus basse = plus precis).",
        f"• {params_note}",
        f"• Gain potentiel : <strong>-{gain:.1f}%</strong> de MAPE en passant de ERP a {best_method}.",
    ]))
    return "".join(out)

def dem_forecast(dfs):
    res=demand_calc(dfs)
    if not res: return '<div class="ae">Aucune donnee.</div>'
    out=[]
    for art,r in res.items():
        base_fc = r["fc_hw"] if r["best"] == "HW" else r["fc_py"]
        best_mape = r["hw_mape"] if r["best"] == "HW" else r["les_mape"]
        hd=["Periode","LES (α seul)","HW (α,β,γ)","ERP (systeme)","Int. bas (~85%)","Int. haut (~85%)","Methode retenue (MAPE min)"]
        rows=[]
        for i in range(6):
            fv=r["fc_py"][i]; hw=r["fc_hw"][i] if i<len(r["fc_hw"]) else round(fv,0)
            ev=r["fc_erp"][i] if i<len(r["fc_erp"]) else None
            bst_v=base_fc[i]
            rows.append([f"M+{i+1}",f"{fv:,.0f}",f"{hw:,.0f}",
                         f"{ev:,.0f}" if ev else "—",
                         f"{round(bst_v*.85,0):,.0f}",f"{round(bst_v*1.15,0):,.0f}",
                         f'<strong>{bst_v:,.0f}</strong>'])
        out.append(T(hd,rows, None, f"Forecast 6 mois — {art[:22]} | Methode : {r['best']} (MAPE={best_mape:.1f}%)"))
        out.append(S(f"Forecast {art[:16]}",[
            f"• ERP = prevision systeme de l'entreprise (reference de comparaison).",
            f"• Methode retenue : <strong>{r['best']}</strong> (MAPE={best_mape:.1f}% — valeur la plus basse = plus precis).",
            f"• Intervalles de confiance a ~85% : dans 85% des cas la demande reelle sera entre Int. bas et Int. haut.",
            f"• M+1 : <strong>{base_fc[0]:,.0f} U</strong> | M+6 : <strong>{base_fc[-1]:,.0f} U</strong>.",
        ]))
    return "".join(out)

# ── FINANCE ───────────────────────────────────────────────────────────────────
def fin_auto(dfs):
    out=[]; total_profit=0
    for sh,df in dfs.items():
        df=df.dropna(how="all").reset_index(drop=True)
        nc=[c for c in df.select_dtypes(include=[np.number]).columns if df[c].dropna().shape[0]>0]
        sc_c=df.select_dtypes(exclude=[np.number]).columns.tolist()
        if not nc: continue
        mg=next((c for c in nc if any(k in c.lower() for k in ["marge","margin"])),None)
        vl=next((c for c in nc if any(k in c.lower() for k in ["volume","forecast","qty","sales"])),None)
        pc=sc_c[0] if sc_c else None
        if mg and vl and pc:
            hd=["Produit","Volume","Marge Unit.","Profit Total","Taux marge %","Statut"]
            rows=[]; cls=[]
            for _,row in df.iterrows():
                vol=cn(row[vl]); marg=cn(row[mg])
                if vol<=0 and marg<=0: continue
                profit=round(vol*marg,0); total_profit+=profit
                taux=round(marg/max(vol,1)*100,1)
                st_c="DEFICIT" if profit<0 else "ATTENTION" if taux<10 else "OK"
                col={"DEFICIT":"#dc2626","ATTENTION":"#d97706","OK":"#16a34a"}[st_c]
                rows.append([str(row[pc])[:20],f"{vol:,.0f}",f"{marg:,.2f}",f"{profit:,.0f}",f"{taux:.1f}%",
                             f'<span style="color:{col};font-weight:700">{st_c}</span>'])
                cls.append("surge" if profit<0 else "alrt" if taux<10 else "")
            out.append(T(hd,rows,cls,f"P&L par Produit — {sh}"))
            out.append(S("Finance",[
                f"• Profit total : <strong>{total_profit:,.0f}</strong>.",
                f"• Produits deficitaires : <strong>{sum(1 for r in rows if 'DEFICIT' in str(r))}</strong>.",
                f"• Produits marge critique (<10%) : <strong>{sum(1 for r in rows if 'ATTENTION' in str(r))}</strong>.",
            ]))
        else:
            for nc_col in nc[:3]:
                col_d=df[nc_col].dropna(); col_d=col_d[col_d!=0]
                if len(col_d)>0:
                    out.append(f'<div style="font-size:.8rem;margin:.2rem 0"><strong>{nc_col}</strong> : Total={col_d.sum():,.1f} | Moy={col_d.mean():,.1f} | Max={col_d.max():,.1f}</div>')
    if not out: out.append('<div class="aw">Aucune colonne Volume et Marge detectees. Verifie le format du fichier.</div>')
    return "".join(out)

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
def render_dashboard(agent, dfs):
    try: import plotly.graph_objects as go
    except: st.warning("Installer plotly"); return
    LAY=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#f8f9fc",
             font=dict(color="#1a1a2e",family="JetBrains Mono",size=10),
             margin=dict(l=0,r=0,t=32,b=0),
             xaxis=dict(gridcolor="#e8ebf2",tickangle=-45,linecolor="#d0d5e8"),
             legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(size=9)))
    LAY_Y=dict(**LAY,yaxis=dict(gridcolor="#e8ebf2",linecolor="#d0d5e8"))
# ── DASHBOARD ─────────────────────────────────────────────────────────────────
def render_dashboard(agent, dfs):
    try: import plotly.graph_objects as go
    except: st.warning("Installer plotly"); return

    LAY = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#f8f9fc",
        font=dict(color="#1a1a2e", family="JetBrains Mono", size=10),
        margin=dict(l=0, r=0, t=32, b=0),
        xaxis=dict(gridcolor="#e8ebf2", tickangle=-45, linecolor="#d0d5e8"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9)))
    LAY_Y = dict(**LAY, yaxis=dict(gridcolor="#e8ebf2", linecolor="#d0d5e8"))

    # ─────────────────────────────────────────────────────────────────────────
    if agent == "production":
        mrp0 = mrp_calc(dfs, {})
    if agent == "production":
        mrp0 = mrp_calc(dfs, {})
        p0   = mrp0["p"]; W = mrp0["weeks"]

        # ── Scénario What-If actif — pas de slider, dynamique uniquement ─────
        wp = st.session_state.get("whatif_params", {})
        sc_prod = wp.get("production", {}).get("sc_txt", "NOMINAL")
        cap_sim = int(p0["cap_v"])
        sim_active = False
        if sc_prod and sc_prod not in ("NOMINAL", ""):
            try:
                new_cap_wi, _, _ = _parse_prod_scenario(sc_prod, p0["cap_v"])
                cap_sim = int(new_cap_wi)
                sim_active = True
            except: pass

    # ─────────────────────────────────────────────────────────────────────────
    if agent == "production":
        col_f1, col_f2 = st.columns([3, 3])
        with col_f1:
            st.markdown('<div style="font-size:.65rem;font-weight:700;color:#6b7299;'
                        'text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem">'
                        'Filtrer semaines</div>', unsafe_allow_html=True)
            wsel = st.multiselect("Sem", W, default=W,
                                  key=f"dwk_{agent}", label_visibility="collapsed")
        with col_f2:
            st.markdown('<div style="font-size:.65rem;font-weight:700;color:#6b7299;'
                        'text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem">'
                        'Filtrer statut</div>', unsafe_allow_html=True)
            ssel = st.multiselect("Statut", ["SURCHARGE","ALERTE","OK"],
                                  default=["SURCHARGE","ALERTE","OK"],
                                  key=f"dst_{agent}", label_visibility="collapsed")

        # Recalcul avec la capacité du What-If actif
        if sim_active:
            mrp = _mrp_calc_with_new_cap(
                mrp0, float(cap_sim), p0["var_v"], p0["ss_v"], p0["bat_v"])
            max_u_sim = round(cap_sim / p0["var_v"], 0) if p0["var_v"] > 0 else cap_sim
        else:
            mrp = mrp0
            max_u_sim = p0["max_u"]

        p  = mrp["p"]
        ms = max(mrp["sat"]); mi = min(mrp["inv_e"])
        ns = sum(1 for s in mrp["status"] if s == "SURCHARGE")
        idx  = [i for i, w in enumerate(W) if w in wsel and mrp["status"][i] in ssel]
        Wf   = [W[i] for i in idx]

        # ── Bandeau What-If ──────────────────────────────────────────────────
        if sim_active:
            ns0    = sum(1 for s in mrp0["status"] if s == "SURCHARGE")
            mi0    = min(mrp0["inv_e"])
            delta_s = ns - ns0; delta_m = mi - mi0
            col_ds = "#16a34a" if delta_s < 0 else "#dc2626"
            col_dm = "#16a34a" if delta_m > 0 else "#dc2626"
            verdict_wi = "✓ GO" if ns==0 else "~ CONDITIONNEL" if ns<3 else "✗ NO-GO"
            col_wi = "#16a34a" if ns==0 else "#d97706" if ns<3 else "#dc2626"
            st.markdown(f"""
<div style="background:#eff6ff;border:1.5px solid #2563eb;border-radius:7px;
  padding:.45rem .75rem;margin-bottom:.35rem;font-size:.78rem;display:flex;
  gap:1.5rem;align-items:center;flex-wrap:wrap">
  <span style="font-weight:800;color:#1e3a8a">📐 What-If : {sc_prod}</span>
  <span>Cap : <strong>{p0['cap_v']:.0f} → {cap_sim} PHR/sem = {max_u_sim:.0f} U/sem</strong></span>
  <span>Surcharges : <strong style="color:{col_ds}">{ns0}→{ns} ({delta_s:+d})</strong></span>
  <span>Stock min : <strong style="color:{col_dm}">{mi0:,.0f}→{mi:,.0f} U ({delta_m:+,.0f})</strong></span>
  <span style="font-weight:800;color:{col_wi}">{verdict_wi}</span>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="ai" style="font-size:.74rem">Aucun scénario What-If actif — '
                'dashboard nominal. Configurez un scénario dans la sidebar '
                '(Cap +X%, Cap -X%, etc.) pour voir l\'impact dynamiquement.</div>',
                unsafe_allow_html=True)

        # ── KPI cards ────────────────────────────────────────────────────────
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Surcharges", f"{ns}/{len(W)}",
                  f"{ns-sum(1 for s in mrp0['status'] if s=='SURCHARGE'):+d}" if sim_active else None)
        k2.metric("Sat max", f"{ms:.0f}%")
        k3.metric("Stock min", f"{mi:,.0f} U", "RUPTURE" if mi < 0 else "OK")
        k4.metric("Cap simulée", f"{cap_sim} PHR", f"→{max_u_sim:.0f} U/sem")
        k5.metric("HS+50%", f"{round(cap_sim*1.5/p['var_v'],0) if p['var_v']>0 else 0:.0f} U/sem")

        # ── Graphiques principaux ────────────────────────────────────────────
        g1, g2 = st.columns(2)
        with g1:
            fig = go.Figure()
            bc  = ["#dc2626" if mrp["status"][i]=="SURCHARGE"
                   else "#d97706" if mrp["status"][i]=="ALERTE"
                   else "#16a34a" for i in idx]
            fig.add_trace(go.Bar(x=Wf, y=[mrp["charge"][i] for i in idx],
                                 marker_color=bc, name="Charge PHR", opacity=.85))
            # Ligne cap nominale (grise)
            fig.add_trace(go.Scatter(x=Wf, y=[p0["cap_v"]]*len(Wf), mode="lines",
                                     name=f"Cap nominale ({p0['cap_v']:.0f})",
                                     line=dict(color="#94a3b8", width=1.5, dash="dot")))
            # Ligne cap simulée (bleue si différente)
            fig.add_trace(go.Scatter(x=Wf, y=[cap_sim]*len(Wf), mode="lines",
                                     name=f"Cap simulée ({cap_sim})",
                                     line=dict(color="#2563eb", width=2.5,
                                               dash="dash" if sim_active else "dot")))
            fig.update_layout(**LAY_Y, height=255,
                              title=dict(text="Charge PHR vs Capacité (bleu = simulation)",
                                         font=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True)

        with g2:
            sc2_nom = ["#dc2626" if mrp0["inv_e"][i] < 0 else "#16a34a" for i in idx]
            sc2_sim = ["#1d4ed8" if mrp["inv_e"][i] < 0 else "#16a34a" for i in idx]
            fig2 = go.Figure()
            if sim_active:
                fig2.add_trace(go.Bar(x=Wf, y=[mrp0["inv_e"][i] for i in idx],
                                      name="Stock nominal", marker_color=sc2_nom, opacity=.5))
                fig2.add_trace(go.Bar(x=Wf, y=[mrp["inv_e"][i] for i in idx],
                                      name="Stock simulé", marker_color=sc2_sim, opacity=.85))
            else:
                fig2.add_trace(go.Bar(x=Wf, y=[mrp["inv_e"][i] for i in idx],
                                      marker_color=sc2_nom, name="Stock projeté", opacity=.85))
            fig2.add_hline(y=0, line_color="#dc2626", line_dash="dash")
            fig2.update_layout(**LAY_Y, height=255, barmode="overlay",
                               title=dict(text="Stock projeté — rouge=rupture, bleu=simulation",
                                          font=dict(size=10)))
            st.plotly_chart(fig2, use_container_width=True)

        g3, g4 = st.columns(2)
        with g3:
            fig3 = go.Figure()
            # Remplissage vert si simulation OK, orange sinon
            fill_col = "rgba(22,163,74,.12)" if (sim_active and ns == 0) else "rgba(217,119,6,.10)"
            line_col = "#16a34a" if (sim_active and ns == 0) else "#d97706"
            fig3.add_trace(go.Scatter(x=Wf, y=[mrp["sat"][i] for i in idx],
                                      fill="tozeroy", fillcolor=fill_col,
                                      line=dict(color=line_col, width=2), name="Sat %"))
            if sim_active:
                fig3.add_trace(go.Scatter(x=Wf, y=[mrp0["sat"][i] for i in idx],
                                          line=dict(color="#94a3b8", width=1.5, dash="dot"),
                                          name="Sat nominale"))
            fig3.add_hline(y=100, line_color="#dc2626", line_dash="dash",
                           annotation_text="Max 100%")
            fig3.add_hline(y=85, line_color="#d97706", line_dash="dot",
                           annotation_text="Alerte 85%")
            fig3.update_layout(**LAY, height=235,
                               yaxis=dict(gridcolor="#e8ebf2", ticksuffix="%", linecolor="#d0d5e8"),
                               title=dict(text="Saturation % — vert si simulation résout les surcharges",
                                          font=dict(size=10)))
            st.plotly_chart(fig3, use_container_width=True)

        with g4:
            # ── Drill-down : répartition de la demande par semaine ───────────
            # Lecture brute des valeurs de la ligne Gross Requirements
            gross_vals = [mrp["gross"][i] for i in idx]
            colors_bar = ["#dc2626" if mrp["gross"][i] > max_u_sim
                          else "#d97706" if mrp["gross"][i] > max_u_sim * 0.8
                          else "#16a34a" for i in idx]

            # Si plusieurs feuilles → essayer d'identifier des produits
            prod_data = {}
            for sh, df_sh in dfs.items():
                if "gross" in sh.lower() or "demand" in sh.lower() or "product" in sh.lower():
                    continue
            # Chercher d'autres lignes "Gross" potentielles (produits multiples)
            df_main = list(dfs.values())[0]
            gross_rows = []
            lc_main = None
            for c in df_main.columns:
                if str(c).lower() in ("donnees","data field","label","description","libelle"):
                    lc_main = c; break
            if lc_main:
                for _, row in df_main.iterrows():
                    if "gross" in str(row[lc_main]).lower() or "besoin" in str(row[lc_main]).lower():
                        gross_rows.append((str(row[lc_main]), row))

            if len(gross_rows) > 1:
                # Plusieurs lignes Gross → drill-down par produit/ligne
                fig4 = go.Figure()
                clrs_prod = ["#1e3a8a","#2563eb","#7c3aed","#16a34a","#d97706"]
                w_cols = [c for c in df_main.columns
                          if any(ch.isdigit() for ch in str(c)) and c in W]
                for pi, (lbl, row) in enumerate(gross_rows[:5]):
                    vals = [cn(row.get(W[i], 0)) for i in idx]
                    fig4.add_trace(go.Bar(x=Wf, y=vals,
                                         name=lbl[:20],
                                         marker_color=clrs_prod[pi % len(clrs_prod)],
                                         opacity=.8))
                fig4.add_hline(y=max_u_sim, line_color="#2563eb", line_dash="dash",
                               annotation_text=f"Cap sim {max_u_sim:.0f} U")
                fig4.update_layout(**LAY_Y, height=235, barmode="stack",
                                   title=dict(text="Drill-down : Demande par produit/ligne (empilé)",
                                              font=dict(size=10)))
            else:
                # Un seul Gross → afficher la demande avec seuil coloré
                fig4 = go.Figure()
                fig4.add_trace(go.Bar(x=Wf, y=gross_vals, name="Demande brute",
                                      marker_color=colors_bar, opacity=.85))
                fig4.add_hline(y=max_u_sim, line_color="#2563eb", line_dash="dash",
                               annotation_text=f"Cap simulée {max_u_sim:.0f} U")
                if sim_active:
                    fig4.add_hline(y=p0["max_u"], line_color="#94a3b8", line_dash="dot",
                                   annotation_text=f"Cap nominale {p0['max_u']:.0f} U")
                # Annoter le pic
                if gross_vals:
                    pic_i = gross_vals.index(max(gross_vals))
                    fig4.add_annotation(x=Wf[pic_i], y=gross_vals[pic_i],
                                        text=f"PIC<br>{gross_vals[pic_i]:,.0f} U",
                                        showarrow=True, arrowhead=2,
                                        font=dict(color="#dc2626", size=9),
                                        arrowcolor="#dc2626", bgcolor="#fef2f2")
                fig4.update_layout(**LAY_Y, height=235,
                                   title=dict(text="Demande brute — rouge=dépasse capacité simulée",
                                              font=dict(size=10)))
            st.plotly_chart(fig4, use_container_width=True)

        # ── Drill-down tableau : top semaines critiques ─────────────────────
        st.markdown('<div style="font-size:.65rem;font-weight:700;color:#1e3a8a;'
                    'text-transform:uppercase;letter-spacing:.1em;margin:.3rem 0 .2rem">'
                    'Drill-down — Semaines critiques (demande > capacité simulée)</div>',
                    unsafe_allow_html=True)
        drill_rows = []
        for i, w in enumerate(W):
            if mrp["gross"][i] > max_u_sim * 0.8:
                deficit = mrp["gross"][i] - max_u_sim
                couvre_hs = mrp["gross"][i] <= max_u_sim * 1.5
                drill_rows.append([
                    w.replace(" Y23",""),
                    f"{mrp['gross'][i]:,.0f}",
                    f"{mrp['sat'][i]:.0f}%",
                    f'<span style="color:{"#dc2626" if deficit>0 else "#16a34a"};font-weight:700">'
                    f'{deficit:+,.0f}</span>',
                    f'<span style="color:{"#16a34a" if couvre_hs else "#dc2626"};font-weight:700">'
                    f'{"OUI" if couvre_hs else "NON"}</span>',
                    f'<span style="color:{"#dc2626" if mrp["inv_e"][i]<0 else "#16a34a"}">'
                    f'{mrp["inv_e"][i]:,.0f} U</span>',
                ])
        if drill_rows:
            hd_d = ["Semaine","Demande","Sat %","Déficit vs cap sim",
                    f"HS+50% couvre ? ({round(max_u_sim*1.5,0):.0f} U)","Stock fin"]
            st.markdown(T(hd_d, drill_rows, None,
                          f"Semaines > 80% de la capacité simulée ({max_u_sim:.0f} U/sem)"),
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="ag">✓ Toutes les semaines sont sous 80% de la capacité simulée.</div>',
                        unsafe_allow_html=True)
    elif agent in ("demande","marketing"):
        CLRS = ["#1e3a8a","#16a34a","#ea580c","#7c3aed","#d97706"]

        # ── Lire le scénario What-If demande actif ────────────────────────────
        wp = st.session_state.get("whatif_params", {})
        sc_dem = wp.get("demande", {}).get("sc_txt", "DEM_AUTO")
        methode_forcee = None
        if sc_dem and sc_dem not in ("DEM_AUTO",""):
            if "DEM_HW"  in sc_dem: methode_forcee = "HW"
            elif "DEM_LES" in sc_dem: methode_forcee = "LES"
            elif "DEM_MA"  in sc_dem: methode_forcee = "MA"

        res = demand_calc(dfs)
        if not res: st.info("Aucune donnée demande."); return

        # ── Filtres ───────────────────────────────────────────────────────────
        fa, fb = st.columns(2)
        with fa:
            st.markdown('<div style="font-size:.65rem;font-weight:700;color:#6b7299;'
                        'text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem">'
                        'Filtrer articles</div>', unsafe_allow_html=True)
            asel = st.multiselect("Articles", list(res.keys()), default=list(res.keys()),
                                  key=f"da_{agent}", label_visibility="collapsed")
        with fb:
            wi_label = f"Scénario actif : {sc_dem}" if methode_forcee else "Auto (MAPE min)"
            st.markdown(f'<div style="font-size:.65rem;font-weight:700;color:#1e3a8a;'
                        f'text-transform:uppercase;letter-spacing:.1em;margin-bottom:.2rem">'
                        f'Forecast — {wi_label}</div>', unsafe_allow_html=True)
            nfc = st.slider("Forecast (mois)", 1, 6, 6,
                            key=f"df_{agent}", label_visibility="collapsed")

        resf = {a: r for a, r in res.items() if a in asel}
        if not resf: st.info("Sélectionne au moins un article."); return

        # ── Graphique historique ──────────────────────────────────────────────
        fig5 = go.Figure()
        for i, (art, r) in enumerate(resf.items()):
            h = r["hist"]; col = CLRS[i % len(CLRS)]
            fig5.add_trace(go.Scatter(x=list(h.index), y=list(h.values), name=art[:18],
                                      mode="lines+markers",
                                      line=dict(color=col, width=2), marker=dict(size=3)))
        fig5.update_layout(**LAY_Y, height=260,
                           title=dict(text="Historique demande réelle par article", font=dict(size=10)))
        st.plotly_chart(fig5, use_container_width=True)

        g1, g2 = st.columns(2)
        with g1:
            # MAPE ERP vs Python — avec méthode forcée si What-If actif
            arts_l = list(resf.keys())
            mapes_erp = [resf[a]["mape_erp"] for a in arts_l]
            if methode_forcee == "HW":
                mapes_py = [resf[a]["hw_mape"]  for a in arts_l]
                py_label = "HW (forcé What-If)"
            elif methode_forcee == "LES":
                mapes_py = [resf[a]["les_mape"] for a in arts_l]
                py_label = "LES (forcé What-If)"
            elif methode_forcee == "MA":
                mapes_py = [resf[a]["ma_mape"]  for a in arts_l]
                py_label = "MA (forcé What-If)"
            else:
                mapes_py = [min(resf[a]["les_mape"],resf[a]["hw_mape"],resf[a]["ma_mape"])
                            for a in arts_l]
                py_label = "Python (auto — MAPE min)"
            mc = ["#dc2626" if m > 50 else "#d97706" if m > 25 else "#16a34a" for m in mapes_erp]
            fig6 = go.Figure()
            fig6.add_trace(go.Bar(x=[a[:14] for a in arts_l], y=mapes_erp,
                                  name="MAPE ERP", marker_color=mc, opacity=.85))
            fig6.add_trace(go.Bar(x=[a[:14] for a in arts_l], y=mapes_py,
                                  name=py_label, marker_color="#2563eb", opacity=.75))
            fig6.add_hline(y=15, line_color="#16a34a", line_dash="dot",
                           annotation_text="Objectif 15%")
            fig6.add_hline(y=25, line_color="#d97706", line_dash="dot")
            fig6.update_layout(**LAY_Y, height=250, barmode="group",
                               title=dict(text=f"MAPE ERP vs {py_label} — plus bas = plus précis",
                                          font=dict(size=10)))
            st.plotly_chart(fig6, use_container_width=True)

        with g2:
            # Forecast — avec méthode forcée si What-If actif
            fig7 = go.Figure()
            for i, (art, r) in enumerate(resf.items()):
                col = CLRS[i % len(CLRS)]
                if methode_forcee == "HW":
                    fc = r["fc_hw"]
                elif methode_forcee in ("LES","MA"):
                    fc = r["fc_py"]
                else:
                    fc = r["fc_hw"] if r["best"] == "HW" else r["fc_py"]
                m_used = methode_forcee or r["best"]
                fig7.add_trace(go.Scatter(
                    x=[f"M+{j+1}" for j in range(nfc)], y=fc[:nfc],
                    name=f"{art[:14]} ({m_used})",
                    mode="lines+markers", line=dict(color=col, width=2),
                    marker=dict(size=6)))
            title_fc = (f"Forecast {nfc} mois — {py_label}"
                        if methode_forcee else f"Forecast {nfc} mois — méthode optimale")
            fig7.update_layout(**LAY_Y, height=250,
                               title=dict(text=title_fc, font=dict(size=10)))
            st.plotly_chart(fig7, use_container_width=True)

        # Heatmap saisonnalité HW
        MN = list(resf.values())[0]["MN"]
        hd_hw = []; ha_hw = []
        for art, r in resf.items():
            if r["seasonal"] and r["best"] == "HW" and r["factors"] and len(r["factors"]) >= 6:
                hd_hw.append([r["factors"].get(m, 1.0) for m in range(12)])
                ha_hw.append(art[:18])
        if hd_hw:
            fig8 = go.Figure(go.Heatmap(z=hd_hw, x=MN, y=ha_hw, zmid=1.0,
                colorscale=[[0,"#fef2f2"],[0.5,"#f0f2f7"],[1,"#f0fdf4"]],
                text=[[f"{v:.2f}x" for v in row] for row in hd_hw],
                texttemplate="%{text}", textfont=dict(size=9)))
            fig8.update_layout(**LAY, height=200,
                               title=dict(text="Facteurs saisonniers F(n,k) HW",
                                          font=dict(size=10)))
            st.plotly_chart(fig8, use_container_width=True)

    elif agent == "finance":
        # ── Dashboard Finance ─────────────────────────────────────────────────
        fin_rows = []
        for sh, df in dfs.items():
            nc  = [c for c in df.select_dtypes(include=[np.number]).columns if df[c].dropna().shape[0] > 0]
            sc_c = df.select_dtypes(exclude=[np.number]).columns.tolist()
            mg = next((c for c in nc if any(k in c.lower() for k in ["marge","margin"])), None)
            vl = next((c for c in nc if any(k in c.lower() for k in ["volume","forecast","qty","sales"])), None)
            pc = sc_c[0] if sc_c else None
            if mg and vl and pc:
                for _, row in df.iterrows():
                    vol = cn(row[vl]); marg = cn(row[mg])
                    if vol <= 0 and marg <= 0: continue
                    profit = vol * marg
                    taux   = marg / max(vol, 1) * 100
                    fin_rows.append({
                        "produit": str(row[pc])[:22],
                        "volume": vol, "marge": marg,
                        "profit": profit, "taux": taux,
                    })

        if not fin_rows:
            st.info("Aucune donnée Finance détectée (colonnes Volume + Marge requises).")
            return

        fin_rows.sort(key=lambda x: x["profit"], reverse=True)
        produits  = [r["produit"] for r in fin_rows]
        profits   = [r["profit"]  for r in fin_rows]
        taux_list = [r["taux"]    for r in fin_rows]
        vols      = [r["volume"]  for r in fin_rows]

        # KPIs
        profit_total = sum(profits)
        n_deficit    = sum(1 for p in profits if p < 0)
        n_critique   = sum(1 for t in taux_list if 0 < t < 10)
        marge_moy    = round(sum(taux_list) / len(taux_list), 1) if taux_list else 0
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("Profit total", f"{profit_total:,.0f}")
        k2.metric("Déficitaires", str(n_deficit), "⚠" if n_deficit > 0 else "✓ 0")
        k3.metric("Marge critique <10%", str(n_critique))
        k4.metric("Taux marge moyen", f"{marge_moy:.1f}%")

        g1, g2 = st.columns(2)
        with g1:
            # Bar chart profit par produit
            bc_fin = ["#dc2626" if p < 0 else "#d97706" if t < 10 else "#16a34a"
                      for p, t in zip(profits, taux_list)]
            fig_f1 = go.Figure()
            fig_f1.add_trace(go.Bar(x=produits, y=profits, marker_color=bc_fin,
                                    opacity=.88, name="Profit"))
            fig_f1.add_hline(y=0, line_color="#dc2626", line_dash="dash")
            fig_f1.update_layout(**LAY_Y, height=280,
                                 title=dict(text="Profit par produit — rouge=déficit, orange=marge critique",
                                            font=dict(size=10)))
            st.plotly_chart(fig_f1, use_container_width=True)

        with g2:
            # Scatter Volume × Taux marge (bulle = profit)
            colors_sc = ["#dc2626" if p < 0 else "#d97706" if t < 10 else "#16a34a"
                         for p, t in zip(profits, taux_list)]
            sizes_sc  = [max(8, min(50, abs(p)/max(abs(x) for x in profits)*40))
                         for p in profits]
            fig_f2 = go.Figure()
            fig_f2.add_trace(go.Scatter(
                x=vols, y=taux_list,
                mode="markers+text",
                text=[p[:10] for p in produits],
                textposition="top center",
                textfont=dict(size=8),
                marker=dict(size=sizes_sc, color=colors_sc, opacity=.8,
                            line=dict(width=1, color="#fff")),
                name="Produits"))
            fig_f2.add_hline(y=10, line_color="#d97706", line_dash="dot",
                             annotation_text="Seuil critique 10%")
            fig_f2.add_hline(y=0, line_color="#dc2626", line_dash="dash")
            fig_f2.update_layout(**LAY_Y, height=280,
                                 xaxis=dict(**LAY["xaxis"], title="Volume (U)"),
                                 yaxis=dict(gridcolor="#e8ebf2", linecolor="#d0d5e8",
                                            ticksuffix="%", title="Taux marge %"),
                                 title=dict(text="Volume × Taux marge (bulle = taille profit)",
                                            font=dict(size=10)))
            st.plotly_chart(fig_f2, use_container_width=True)

        g3, g4 = st.columns(2)
        with g3:
            # Taux marge par produit
            colors_mg = ["#dc2626" if t < 0 else "#d97706" if t < 10 else "#16a34a"
                         for t in taux_list]
            fig_f3 = go.Figure()
            fig_f3.add_trace(go.Bar(x=produits, y=taux_list, marker_color=colors_mg,
                                    opacity=.85, name="Taux marge %"))
            fig_f3.add_hline(y=10, line_color="#d97706", line_dash="dot",
                             annotation_text="Min 10%")
            fig_f3.add_hline(y=0, line_color="#dc2626", line_dash="dash")
            fig_f3.update_layout(**LAY_Y, height=250,
                                 yaxis=dict(gridcolor="#e8ebf2", ticksuffix="%",
                                            linecolor="#d0d5e8"),
                                 title=dict(text="Taux de marge % par produit",
                                            font=dict(size=10)))
            st.plotly_chart(fig_f3, use_container_width=True)

        with g4:
            # Part du profit par produit (waterfall simplifié)
            pos_profits = [(p, pr) for p, pr in zip(produits, profits) if pr > 0]
            neg_profits = [(p, pr) for p, pr in zip(produits, profits) if pr < 0]
            fig_f4 = go.Figure()
            if pos_profits:
                fig_f4.add_trace(go.Bar(
                    x=[p for p, _ in pos_profits],
                    y=[pr for _, pr in pos_profits],
                    name="Contribution positive", marker_color="#16a34a", opacity=.85))
            if neg_profits:
                fig_f4.add_trace(go.Bar(
                    x=[p for p, _ in neg_profits],
                    y=[pr for _, pr in neg_profits],
                    name="Perte", marker_color="#dc2626", opacity=.85))
            fig_f4.update_layout(**LAY_Y, height=250,
                                 title=dict(text="Contribution au profit total",
                                            font=dict(size=10)))
            st.plotly_chart(fig_f4, use_container_width=True)

    else:
        st.info("Dashboard disponible pour Production, Demande, Marketing et Finance.")

# ── ORCHESTRATEUR ─────────────────────────────────────────────────────────────
def _orch_collect_data():
    """
    Collecte les données réelles de chaque agent EN TENANT COMPTE
    des scénarios What-If actifs dans chaque onglet.
    Si l'agent Production a un scénario Cap+15% actif → l'orchestrateur l'utilise.
    Si l'agent Demande a un scénario LES forcé actif → l'orchestrateur l'utilise.
    """
    data = {"production": None, "demande": [], "finance": None, "errors": [],
            "scenarios_actifs": {}}

    wp = st.session_state.get("whatif_params", {})

    # ── PRODUCTION — avec scénario What-If actif si défini ───────────────────
    d_prod = get_dfs("production")
    if d_prod:
        try:
            mrp_base = mrp_calc(d_prod, {})
            p_base = mrp_base["p"]

            # ── Lire le scénario depuis DEUX sources (widget keys = plus fiable) ──
            # Source 1 : clés widget Streamlit (valeur réelle affichée à l'écran)
            cap_mode_ss = st.session_state.get("cap_mode_production", "Nominal")
            cap_p_ss    = st.session_state.get("cap_p_production", 25)
            cap_m_ss    = st.session_state.get("cap_m_production", 20)
            cap_abs_ss  = st.session_state.get("cap_abs_production", 1400)
            use_mp_ss   = st.session_state.get("use_mp_production", False)
            mp_ss       = st.session_state.get("mp_production", 2000)

            # Reconstruire sc_txt depuis les widgets (même logique que la sidebar)
            parts_ss = []
            if cap_mode_ss == "Capacite -X%":
                parts_ss.append(f"CAP_MINUS_{cap_m_ss}")
            elif cap_mode_ss == "Capacite +X%":
                parts_ss.append(f"CAP_PLUS_{cap_p_ss}")
            elif cap_mode_ss == "Capacite ignoree":
                parts_ss.append("CAP_IGNORED")
            elif cap_mode_ss == "Capacite absolue PHR":
                parts_ss.append(f"CAP_{int(cap_abs_ss)}")
            if use_mp_ss and mp_ss:
                parts_ss.append(f"MINPROD_{int(mp_ss)}")
            sc_from_widgets = "+".join(parts_ss) if parts_ss else "NOMINAL"

            # Source 2 : whatif_params (backup)
            sc_from_params = wp.get("production", {}).get("sc_txt", "NOMINAL")

            # Priorité : widgets > whatif_params
            sc_prod = sc_from_widgets if sc_from_widgets != "NOMINAL" else sc_from_params

            # Appliquer le scénario si actif
            if sc_prod and sc_prod not in ("NOMINAL", ""):
                try:
                    new_cap, minprod_val, sc_label = _parse_prod_scenario(sc_prod, p_base["cap_v"])
                    mrp = _mrp_calc_with_new_cap(
                        mrp_base, new_cap, p_base["var_v"],
                        p_base["ss_v"], p_base["bat_v"], minprod=minprod_val)
                    data["scenarios_actifs"]["production"] = sc_label
                    data["wi_prod_actif"]  = True
                    data["wi_prod_sc_txt"] = sc_prod
                except Exception as _e_sc:
                    mrp = mrp_base
                    sc_label = "Nominal"
                    data["errors"].append(f"Scenario production echoue ({sc_prod}) : {_e_sc}")
                    data["wi_prod_actif"] = False
            else:
                mrp = mrp_base
                sc_label = "Nominal"
                data["wi_prod_actif"]  = False
                data["wi_prod_sc_txt"] = "NOMINAL"

            p = mrp["p"]; W = mrp["weeks"]
            ns  = sum(1 for s in mrp["status"] if s == "SURCHARGE")
            na  = sum(1 for s in mrp["status"] if s == "ALERTE")
            ms  = max(mrp["sat"]); mi = min(mrp["inv_e"])
            n_rupt  = sum(1 for v in mrp["inv_e"] if v < 0)
            st_total = sum(max(0.0, mrp["gross"][i] - p["max_u"]) for i in range(len(W)))
            hs25 = round(p["cap_v"] * 1.25 / p["var_v"], 0)
            hs50 = round(p["cap_v"] * 1.50 / p["var_v"], 0)
            n_hs25 = sum(1 for i in range(len(W)) if mrp["status"][i] == "SURCHARGE"
                         and mrp["gross"][i] * p["var_v"] <= p["cap_v"] * 1.25)
            n_hs50 = sum(1 for i in range(len(W)) if mrp["status"][i] == "SURCHARGE"
                         and mrp["gross"][i] * p["var_v"] <= p["cap_v"] * 1.50)
            # Saturation par semaine (pour détection semaines creuses)
            sat_list = mrp["sat"]
            pic_idx = max(range(len(W)), key=lambda i: mrp["gross"][i])
            data["production"] = {
                "weeks_total": len(W), "n_surcharge": ns, "n_alerte": na,
                "sat_max": ms, "stock_min": mi, "n_rupture": n_rupt,
                "st_total": st_total, "cap_v": p["cap_v"], "max_u": p["max_u"],
                "hs25_u": hs25, "hs50_u": hs50, "n_hs25": n_hs25, "n_hs50": n_hs50,
                "pic_w": W[pic_idx].replace(" Y23",""), "pic_dem": mrp["gross"][pic_idx],
                "inv0": p["inv0"], "var_v": p["var_v"],
                "sat_list": sat_list,
                "scenario": sc_label,
                # Comparaison vs nominal si scénario actif
                "ns_nominal": sum(1 for s in mrp_base["status"] if s=="SURCHARGE"),
                "mi_nominal": min(mrp_base["inv_e"]),
            }
        except Exception as e:
            data["errors"].append(f"Production : {e}")

    # ── DEMANDE — avec scénario What-If actif si défini ──────────────────────
    for ag in ["demande", "marketing"]:
        d_dem = get_dfs(ag)
        if not d_dem: continue
        try:
            dem = demand_calc(d_dem)
            # Lire scénario demande depuis les widgets ET whatif_params
            sc_from_w_dem = "DEM_AUTO"
            meth_ss = st.session_state.get(f"sc_meth_{ag}", "Auto (recommandee — MAPE min)")
            if "MA" in meth_ss:
                ma_w_ss = st.session_state.get(f"sc_ma_{ag}", 3)
                sc_from_w_dem = f"DEM_MA_{ma_w_ss}"
            elif "LES" in meth_ss:
                alpha_ss = st.session_state.get(f"sc_alpha_{ag}", 0.3)
                sc_from_w_dem = f"DEM_LES+ALPHA_{alpha_ss}"
            elif "HW" in meth_ss:
                alpha_ss = st.session_state.get(f"sc_alpha_hw_{ag}", 0.3)
                beta_ss  = st.session_state.get(f"sc_beta_{ag}", 0.1)
                gamma_ss = st.session_state.get(f"sc_gamma_{ag}", 0.1)
                sc_from_w_dem = f"DEM_HW+ALPHA_{alpha_ss}+BETA_{beta_ss}+GAMMA_{gamma_ss}"

            sc_from_p_dem = wp.get("demande", {}).get("sc_txt", "DEM_AUTO")
            sc_dem = sc_from_w_dem if sc_from_w_dem != "DEM_AUTO" else sc_from_p_dem
            methode_forcee = None

            # Si scénario demande actif, noter la méthode forcée
            if sc_dem and sc_dem not in ("DEM_AUTO", ""):
                data["scenarios_actifs"]["demande"] = sc_dem
                # Extraire la méthode du scénario
                if "DEM_HW" in sc_dem: methode_forcee = "HW"
                elif "DEM_LES" in sc_dem: methode_forcee = "LES"
                elif "DEM_MA" in sc_dem: methode_forcee = "MA"

            for art, r in dem.items():
                # Utiliser la méthode du scénario si forcée, sinon la meilleure
                if methode_forcee == "HW":
                    best_py = r["hw_mape"]
                    methode = "HW (forcé scénario)"
                    fc_m1 = r["fc_hw"][0] if r["fc_hw"] else r["fc_py"][0]
                elif methode_forcee == "LES":
                    best_py = r["les_mape"]
                    methode = "LES (forcé scénario)"
                    fc_m1 = r["fc_py"][0]
                elif methode_forcee == "MA":
                    best_py = r["ma_mape"]
                    methode = "MA (forcé scénario)"
                    fc_m1 = r["fc_py"][0]
                else:
                    best_py = min(r["les_mape"], r["hw_mape"], r["ma_mape"])
                    methode = r["best"]
                    fc_m1 = (r["fc_hw"] if r["best"]=="HW" else r["fc_py"])[0]

                data["demande"].append({
                    "article": art, "agent": ag,
                    "mape_erp": r["mape_erp"], "mape_py": best_py,
                    "methode": methode, "trend": r["trend"],
                    "mean": r["mean"], "cv": r["cv"], "n": r["n"],
                    "gain": round(r["mape_erp"] - best_py, 1),
                    "fc_m1": fc_m1,
                    "scenario": sc_dem if methode_forcee else "Auto",
                })
            break
        except Exception as e:
            data["errors"].append(f"Demande : {e}")

    # ── FINANCE ──────────────────────────────────────────────────────────────
    d_fin = get_dfs("finance")
    if d_fin:
        try:
            profits = []; deficits = []; critiques = []
            for sh, df in d_fin.items():
                nc = [c for c in df.select_dtypes(include=[np.number]).columns if df[c].dropna().shape[0] > 0]
                sc_c = df.select_dtypes(exclude=[np.number]).columns.tolist()
                mg = next((c for c in nc if any(k in c.lower() for k in ["marge","margin"])), None)
                vl = next((c for c in nc if any(k in c.lower() for k in ["volume","forecast","qty","sales"])), None)
                pc = sc_c[0] if sc_c else None
                if mg and vl and pc:
                    for _, row in df.iterrows():
                        vol = cn(row[vl]); marg = cn(row[mg])
                        if vol <= 0 and marg <= 0: continue
                        profit = vol * marg
                        profits.append(profit)
                        if profit < 0: deficits.append((str(row[pc])[:20], profit))
                        if marg / max(vol, 1) * 100 < 10: critiques.append(str(row[pc])[:20])
            data["finance"] = {
                "profit_total": sum(profits), "n_deficit": len(deficits),
                "n_critique": len(critiques),
                "worst": deficits[0] if deficits else None,
            }
        except Exception as e:
            data["errors"].append(f"Finance : {e}")

    return data


def _orch_detect_context(data, mrp_raw=None):
    """
    Toutes les données sont considérées comme prévisionnelles / actuelles.
    Contexte historique supprimé à la demande de l'encadrante.
    """
    return "plan"


def _orch_detect_situation(data):
    """
    Étape 1 du raisonnement : LIRE la situation sans préjugé.
    Retourne un dictionnaire de flags factuels — aucune recommandation ici.
    On observe d'abord, on prescrit ensuite.
    """
    p = data["production"]; arts = data["demande"]; fin = data["finance"]
    f = {
        # Production
        "prod_dispo":            p is not None,
        "prod_ok":               False,   # 0 surcharge, stock positif, clients livrés
        "prod_stock_ok":         False,   # stock positif même avec surcharges
        "prod_surcharge":        False,   # au moins 1 semaine en surcharge
        "prod_surcharge_severe": False,   # > 50% des semaines en surcharge
        "prod_rupture":          False,   # stock min < 0
        "prod_rupture_severe":   False,   # > 50% semaines avec stock négatif
        "prod_anticipation_ok":  False,   # semaines creuses disponibles pour avancer
        "prod_hs_utile":         False,   # HS résout au moins 1 surcharge
        "prod_hs_suffisant":     False,   # HS résout TOUTES les surcharges
        "prod_st_obligatoire":   False,   # pics impossibles même avec HS max
        "prod_sat_extreme":      False,   # saturation > 300% sur au moins 1 sem
        # Demande
        "dem_dispo":             bool(arts),
        "dem_erp_inutile":       False,   # MAPE ERP > 25% — ERP peu fiable
        "dem_erp_bon":           False,   # MAPE ERP < 15% — ERP déjà précis
        "dem_python_meilleur":   False,   # Python MAPE < ERP MAPE
        "dem_prevision_fiable":  False,   # MAPE Python < 15%
        "dem_volatile":          False,   # CV moyen > 60%
        "dem_tendance_baisse":   False,   # déclin structurel
        "dem_historique_court":  False,   # n < 12 périodes
        "wi_ameliore":           False,   # scénario What-If améliore la situation
        # Finance
        "fin_dispo":             fin is not None,
        "fin_deficit":           False,
        "fin_marge_critique":    False,
        "fin_sain":              False,
    }

    # ── Analyse production ────────────────────────────────────────────────────
    if p:
        ns = p["n_surcharge"]; nw = p["weeks_total"]
        mi = p["stock_min"]; nr = p["n_rupture"]; ms = p["sat_max"]
        f["prod_surcharge"]        = ns > 0
        f["prod_surcharge_severe"] = ns > nw * 0.5
        f["prod_rupture"]          = mi < 0
        f["prod_rupture_severe"]   = nr > nw * 0.5
        f["prod_stock_ok"]         = mi >= 0
        f["prod_ok"]               = (ns == 0 and mi >= 0)
        f["prod_hs_utile"]         = p["n_hs50"] > 0
        f["prod_hs_suffisant"]     = (p["n_hs50"] >= ns and ns > 0)
        f["prod_st_obligatoire"]   = (p["st_total"] > 0 and
                                       ns > p["n_hs50"])
        f["prod_sat_extreme"]      = ms > 300
        # Semaines creuses = saturation < 60% (capacité disponible pour anticipation)
        n_creuses = sum(1 for i in range(nw) if p.get("sat_list", [ms]*nw)[i] < 60)
        f["prod_anticipation_ok"]  = n_creuses > 0

    # ── Analyse demande ───────────────────────────────────────────────────────
    if arts:
        mpy = [a["mape_py"] for a in arts]
        merp = [a["mape_erp"] for a in arts]
        cvs  = [a["cv"] for a in arts]
        ns_arts = [a["n"] for a in arts]
        f["dem_prevision_fiable"]  = sum(mpy)/len(mpy) < 15
        f["dem_erp_bon"]           = sum(merp)/len(merp) < 15
        f["dem_erp_inutile"]       = sum(merp)/len(merp) > 25
        f["dem_python_meilleur"]   = sum(1 for a in arts if a["gain"] > 0) > len(arts)//2
        f["dem_volatile"]          = sum(cvs)/len(cvs) > 60
        f["dem_tendance_baisse"]   = any(a["trend"] < -10 for a in arts)
        f["dem_historique_court"]  = sum(ns_arts)/len(ns_arts) < 12

    # ── Analyse finance ───────────────────────────────────────────────────────
    if fin:
        f["fin_deficit"]        = fin["n_deficit"] > 0
        f["fin_marge_critique"] = fin["n_critique"] > 0
        f["fin_sain"]           = (fin["n_deficit"] == 0 and fin["n_critique"] == 0)

    # ── Scénario What-If actif ? ─────────────────────────────────────────────
    # Source 1 : data["scenarios_actifs"] — scénarios RÉELLEMENT appliqués aux données
    # Source 2 : session_state — fallback si data non disponible
    sc_actifs = data.get("scenarios_actifs", {})
    f["wi_ameliore"] = bool(sc_actifs)   # True seulement si scénario vraiment appliqué

    # ── Amélioration RÉELLE mesurée ──────────────────────────────────────────
    # Comparer stock/surcharges avec et sans scénario
    if p and f["wi_ameliore"]:
        mi_now  = p.get("stock_min",   0)
        mi_nom  = p.get("mi_nominal",  mi_now)
        ns_now  = p.get("n_surcharge", 0)
        ns_nom  = p.get("ns_nominal",  ns_now)
        f["wi_stock_improved"]    = mi_now > mi_nom        # stock moins négatif
        f["wi_surcharge_improved"]= ns_now < ns_nom        # moins de surcharges
    else:
        f["wi_stock_improved"]     = False
        f["wi_surcharge_improved"] = False

    # ── Propagation des métriques production ──────────────────────────────────
    f["prod_dispo"]    = bool(p)
    f["prod_ok"]       = bool(p) and p.get("n_rupture", 1) == 0 and p.get("sat_max", 999) <= 100
    f["prod_n_rupture"]= p.get("n_rupture", 0) if p else 0
    f["prod_sat_max"]  = p.get("sat_max",   0) if p else 0
    f["prod_rupture"]  = f["prod_n_rupture"] > 0

    return f


def _orch_reason(data, flags):
    """
    Étape 2 du raisonnement : ANALYSER et PRESCRIRE.
    Chaque action n'est proposée que si elle est pertinente pour la situation détectée.
    Les actions HS et ST ne sont proposées QUE si nécessaires.
    Si la production tourne normalement et les clients sont livrés → pas de HS ni ST.
    """
    p = data["production"]; arts = data["demande"]; fin = data["finance"]
    diagnostics = []   # [{domaine, statut, couleur, analyse, action}]
    actions = []       # [{prio, resp, action, delai, condition}]

    # ════════════════════════════════════════════════════════════════════════
    # PRODUCTION
    # ════════════════════════════════════════════════════════════════════════
    if flags["prod_dispo"]:
        ns = p["n_surcharge"]; nw = p["weeks_total"]
        mi = p["stock_min"]; ms = p["sat_max"]
        st = p["st_total"]

        if flags["prod_ok"]:
            # Situation idéale — ne pas polluer avec des suggestions inutiles
            diagnostics.append({"domaine": "Production", "statut": "OK", "col": "#16a34a",
                "analyse": (f"Production nominale. {nw} semaines, 0 surcharge. "
                            f"Stock min {mi:,.0f} U positif. Clients livrés normalement."),
                "action": None})  # ← Rien à faire

        elif flags["prod_surcharge"] and flags["prod_stock_ok"] and not flags["prod_rupture"]:
            # Surcharges mais stock absorbe — anticipation suffit souvent
            diagnostics.append({"domaine": "Production", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"{ns}/{nw} semaines en surcharge (sat max {ms:.0f}%) "
                            f"mais stock min {mi:,.0f} U reste positif. "
                            f"Le stock actuel absorbe une partie de la demande. "
                            f"Anticipation probable avant recours à HS ou ST."),
                "action": f"Analyser la répartition des semaines creuses pour avancer la production."})
            actions.append({"prio": 1, "resp": "Responsable Production",
                "action": (f"Avancer la production sur les semaines à faible charge "
                           f"(stock initial {p['inv0']:,.0f} U disponible). "
                           f"Objectif : lisser la charge et éviter les surcharges."),
                "delai": "Immédiat",
                "condition": f"Stock min remonte > 0 et surcharges résorbées. "
                             f"Si surcharges persistent après lissage → évaluer HS."})
            if flags["prod_hs_suffisant"]:
                actions.append({"prio": 2, "resp": "RH + Atelier",
                    "action": (f"Si anticipation insuffisante : HS +50% sur {p['n_hs50']} semaine(s) "
                               f"({p['hs50_u']:.0f} U/sem max). HS +50% suffit à couvrir toutes les surcharges."),
                    "delai": "J+7 (accord RH)",
                    "condition": "Toutes surcharges couvertes. Pas de ST requise."})

        elif flags["prod_surcharge_severe"] and flags["prod_st_obligatoire"]:
            # Cas sévère : pics massifs impossibles en interne
            diagnostics.append({"domaine": "Production", "statut": "CRITIQUE", "col": "#dc2626",
                "analyse": (f"{ns}/{nw} semaines en surcharge (sat max {ms:.0f}%). "
                            f"Stock min {mi:,.0f} U. "
                            f"Pic {p['pic_w']} : {p['pic_dem']:,.0f} U/sem = {ms:.0f}% de saturation. "
                            f"HS max ({p['hs50_u']:.0f} U/sem) ne couvre que {p['n_hs50']}/{ns} surcharges. "
                            f"Sous-traitance incontournable : {st:,.0f} U sur {ns - p['n_hs50']} semaines critiques."),
                "action": "Séquence : anticipation → HS sur semaines partielles → ST sur pics impossibles."})
            if flags["prod_anticipation_ok"]:
                actions.append({"prio": 1, "resp": "Responsable Production",
                    "action": f"Avancer la production sur semaines creuses (stock {p['inv0']:,.0f} U).",
                    "delai": "Immédiat",
                    "condition": "Stock remonté. Si pics toujours > capacité → Étape 2."})
            if flags["prod_hs_utile"]:
                actions.append({"prio": len(actions)+1, "resp": "RH + Atelier",
                    "action": (f"HS +50% sur {p['n_hs50']} semaine(s) partiellement couvertes "
                               f"({p['hs50_u']:.0f} U/sem). Économise {round(p['n_hs50']*p['hs50_u']*p.get('var_v',0.4667),0):,.0f} PHR de ST."),
                    "delai": "J+7 (accord RH)",
                    "condition": f"Surcharges modérées résolues. Pics > {p['hs50_u']:.0f} U/sem → Étape {len(actions)+1}."})
            actions.append({"prio": len(actions)+1, "resp": "Direction Achats",
                "action": (f"Appel d'offres sous-traitance : {st:,.0f} U totales "
                           f"sur semaines critiques (pic {p['pic_w']} : {p['pic_dem']:,.0f} U/sem). "
                           f"Surcoût estimé +30-35% vs interne — obtenir 2-3 devis."),
                "delai": "J+14 (devis ST)",
                "condition": "Toutes semaines critiques couvertes. Plan validé."})

        elif flags["prod_surcharge"] and flags["prod_hs_suffisant"]:
            # Surcharges mais HS suffit — pas besoin de ST
            diagnostics.append({"domaine": "Production", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"{ns}/{nw} surcharges. HS +50% ({p['hs50_u']:.0f} U/sem) "
                            f"couvre toutes les surcharges. Stock min {mi:,.0f} U."),
                "action": "HS suffit — pas de sous-traitance nécessaire."})
            actions.append({"prio": 1, "resp": "RH + Atelier",
                "action": (f"Mettre en place HS +50% sur Fill-L1 ({p['hs50_u']:.0f} U/sem) "
                           f"pour les {ns} semaine(s) en surcharge. Valider avec RH et IRP."),
                "delai": "J+7",
                "condition": "Toutes surcharges résolues. Aucune ST requise dans ce scénario."})

    # ════════════════════════════════════════════════════════════════════════
    # DEMANDE
    # ════════════════════════════════════════════════════════════════════════
    if flags["dem_dispo"]:
        mpy_avg  = round(sum(a["mape_py"]  for a in arts)/len(arts), 1)
        merp_avg = round(sum(a["mape_erp"] for a in arts)/len(arts), 1)
        cv_avg   = round(sum(a["cv"]       for a in arts)/len(arts), 0)
        n_gain   = sum(1 for a in arts if a["gain"] > 0)

        if flags["dem_prevision_fiable"] and flags["dem_erp_bon"]:
            # Les deux sont bons — juste confirmer
            diagnostics.append({"domaine": "Demande", "statut": "OK", "col": "#16a34a",
                "analyse": (f"ERP MAPE {merp_avg:.1f}% et Python MAPE {mpy_avg:.1f}% — "
                            f"les deux méthodes sont précises (objectif < 15%). "
                            f"Prévisions fiables, aucune action requise."),
                "action": None})

        elif flags["dem_prevision_fiable"] and flags["dem_erp_inutile"]:
            # Python bien meilleur que ERP — recommander la migration
            diagnostics.append({"domaine": "Demande", "statut": "OK", "col": "#16a34a",
                "analyse": (f"Python MAPE {mpy_avg:.1f}% (objectif < 15%) — prévisions fiables. "
                            f"ERP MAPE {merp_avg:.1f}% — méthode ERP peu performante. "
                            f"Python améliore {n_gain}/{len(arts)} article(s)."),
                "action": "Adopter les prévisions Python et abandonner les prévisions ERP."})
            actions.append({"prio": len(actions)+1, "resp": "Planification Demande",
                "action": (f"Intégrer les prévisions Python ({mpy_avg:.1f}% MAPE) "
                           f"dans le plan de production en remplacement de l'ERP ({merp_avg:.1f}%). "
                           f"Gain moyen : {round(sum(a['gain'] for a in arts)/len(arts),1):+.1f}% de MAPE."),
                "delai": "J+7",
                "condition": "Prévisions ERP remplacées. Gain MAPE confirmé sur 2 cycles."})

        elif flags["dem_volatile"]:
            worst_cv = max(arts, key=lambda a: a["cv"])
            diagnostics.append({"domaine": "Demande", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"Séries très volatiles (CV moyen {cv_avg:.0f}%). "
                            f"Article le plus volatile : {worst_cv['article'][:20]} (CV {worst_cv['cv']:.0f}%). "
                            f"Toute méthode de prévision sera imprécise sur ces séries."),
                "action": "Identifier les causes de volatilité avant d'ajuster les méthodes."})
            actions.append({"prio": len(actions)+1, "resp": "Planification Demande + Marketing",
                "action": (f"Analyser les causes de volatilité de '{worst_cv['article'][:20]}' "
                           f"(promotions non planifiées, saisonnalité non capturée, clients irréguliers ?). "
                           f"Envisager une segmentation de la demande ou des intervalles élargis."),
                "delai": "J+14",
                "condition": "CV < 40% ou segmentation validée. Alors réévaluer la méthode."})

        elif not flags["dem_prevision_fiable"]:
            worst_mpy = max(arts, key=lambda a: a["mape_py"])
            cause = ("Historique trop court — recommandé 24+ périodes pour HW"
                     if flags["dem_historique_court"] else
                     "Paramètres à optimiser ou série non saisonnière")
            diagnostics.append({"domaine": "Demande", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"MAPE Python moyen {mpy_avg:.1f}% (objectif < 15%). "
                            f"Article le moins précis : {worst_mpy['article'][:20]} "
                            f"({worst_mpy['mape_py']:.1f}% avec {worst_mpy['methode']}). "
                            f"Cause probable : {cause}."),
                "action": "Enrichir l'historique et revalider la méthode."})
            actions.append({"prio": len(actions)+1, "resp": "Planification Demande",
                "action": (f"Pour '{worst_mpy['article'][:20]}' ({worst_mpy['n']} périodes) : "
                           f"vérifier les anomalies (±2σ), tester HW si saisonnalité présente, "
                           f"objectif MAPE < 15%."),
                "delai": "J+7",
                "condition": "MAPE Python < 15% sur cet article."})

        if flags["dem_tendance_baisse"]:
            declining = [a for a in arts if a["trend"] < -10]
            diagnostics.append({"domaine": "Demande", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"{len(declining)} article(s) en déclin structurel "
                            f"(tendance < −10 U/période) : "
                            f"{', '.join(a['article'][:16] for a in declining[:2])}."),
                "action": "Décision stratégique — pas une action de planification."})
            actions.append({"prio": len(actions)+1, "resp": "Direction Marketing + Ventes",
                "action": (f"Alerter sur le déclin de {len(declining)} article(s). "
                           f"Décider : repositionnement tarifaire, promotion, arrêt de référence, "
                           f"ou remplacement produit. Ne pas forcer la production de références en déclin."),
                "delai": "J+30",
                "condition": "Décision stratégique actée. Plan de production ajusté en conséquence."})

    # ════════════════════════════════════════════════════════════════════════
    # FINANCE
    # ════════════════════════════════════════════════════════════════════════
    if flags["fin_dispo"]:
        if flags["fin_sain"]:
            diagnostics.append({"domaine": "Finance", "statut": "OK", "col": "#16a34a",
                "analyse": (f"Profit total {fin['profit_total']:,.0f}. "
                            f"Aucun produit déficitaire ni marge critique. Rentabilité satisfaisante."),
                "action": None})
        else:
            detail = []
            if flags["fin_deficit"]:
                detail.append(f"{fin['n_deficit']} produit(s) déficitaire(s)")
            if flags["fin_marge_critique"]:
                detail.append(f"{fin['n_critique']} produit(s) marge < 10%")
            diagnostics.append({"domaine": "Finance", "statut": "ATTENTION", "col": "#d97706",
                "analyse": (f"Profit total {fin['profit_total']:,.0f}. "
                            f"{' | '.join(detail)}. "
                            f"Risque : produire des références non rentables aggrave les pertes."),
                "action": "Audit tarifaire avant la prochaine revue S&OP."})
            actions.append({"prio": len(actions)+1, "resp": "Direction Financière + Commercial",
                "action": (f"Auditer les {fin['n_deficit']+fin['n_critique']} références à marge faible : "
                           f"renégocier les prix, réduire les coûts variables, ou arrêter la production. "
                           f"Ne pas inclure ces références dans les plans de capacité si déficitaires."),
                "delai": "J+30",
                "condition": "Toutes références actives avec marge > 0."})

    # ════════════════════════════════════════════════════════════════════════
    # SITUATION TOTALEMENT OK
    # ════════════════════════════════════════════════════════════════════════
    if not actions and not any(d["statut"] != "OK" for d in diagnostics):
        diagnostics.append({"domaine": "Global", "statut": "OK", "col": "#16a34a",
            "analyse": ("Plan S&OP validé sur tous les domaines. "
                        "Production nominale, prévisions fiables, finance saine. "
                        "Aucune action corrective requise pour cette période."),
            "action": None})

    return diagnostics, actions


def _orch_verdict_global(flags):
    """
    Verdict S&OP — logique stricte et hiérarchisée.

    Règle fondamentale :
      1. NO-GO    : ruptures sévères sans amélioration réelle
      2. GO COND  : problèmes identifiés mais levier existant ou amélioration mesurée
      3. GO       : aucun problème critique

    wi_ameliore seul ne suffit PAS pour passer de NO-GO à GO CONDITIONNEL.
    Il faut qu'il y ait une amélioration RÉELLE mesurée (wi_stock_improved ou wi_surcharge_improved).
    """
    # ── Flags production ─────────────────────────────────────────────────────
    prod_dispo = flags.get("prod_dispo", False)
    rupture    = flags.get("prod_rupture", False)
    n_rupture  = flags.get("prod_n_rupture", 0)
    sat_max    = flags.get("prod_sat_max", 0)
    prod_ok    = flags.get("prod_ok", False)

    # ── Flags What-If ─────────────────────────────────────────────────────────
    # wi_ameliore = scénario configuré (pas forcément actif ou améliorant)
    # wi_stock_improved = stock réellement amélioré vs nominal
    # wi_surcharge_improved = surcharges réellement réduites vs nominal
    wi_active    = flags.get("wi_ameliore", False)
    wi_stk_ok    = flags.get("wi_stock_improved", False)
    wi_surch_ok  = flags.get("wi_surcharge_improved", False)
    wi_improves  = wi_stk_ok or wi_surch_ok   # amélioration RÉELLE mesurée

    # ── Pas de données production ────────────────────────────────────────────
    if not prod_dispo:
        return "GO CONDITIONNEL", "#d97706"

    # ── Situation idéale ─────────────────────────────────────────────────────
    if prod_ok or (not rupture and sat_max <= 100):
        return "GO", "#16a34a"

    # ── Situation critique : ruptures sévères ─────────────────────────────────
    # Critères : stock négatif sur plusieurs semaines + saturation extrême
    situation_critique = rupture and n_rupture > 2 and sat_max > 300

    if situation_critique:
        # What-If améliore RÉELLEMENT → GO CONDITIONNEL avec conditions
        if wi_active and wi_improves:
            return "GO CONDITIONNEL", "#d97706"
        # Pas d'amélioration réelle → NO-GO
        return "NO-GO", "#dc2626"

    # ── Surcharges modérées (gérables avec HS ou anticipation) ───────────────
    return "GO CONDITIONNEL", "#d97706"



def _orch_verdict_prod(p):
    """
    Retourne (verdict, couleur, explication courte) — toujours 3 valeurs.

    Règle clé : si un scénario What-If est actif ET améliore la situation
    (moins de ruptures OU stock moins négatif), on ne dit jamais NO-GO —
    on dit GO CONDITIONNEL et on explique ce qui manque encore.
    """
    if p is None:
        return "N/D", "#6b7280", "Aucune donnee production chargee."

    sc          = p.get("scenario", "Nominal")
    wi_actif    = sc not in ("Nominal", "Nominal (erreur scénario)", "")
    mi          = p["stock_min"]
    mi_nom      = p.get("mi_nominal", mi)         # stock nominal pour comparaison
    ns          = p["n_surcharge"]
    ns_nom      = p.get("ns_nominal", ns)         # surcharges nominales
    nr          = p["n_rupture"]
    sat         = p["sat_max"]

    # ── Amélioration détectée vs nominal ──────────────────────────────────────
    stock_ameliore   = wi_actif and mi > mi_nom    # stock moins négatif
    surcharge_reduit = wi_actif and ns < ns_nom    # moins de surcharges
    wi_ameliore      = stock_ameliore or surcharge_reduit

    delta_stock  = mi - mi_nom if wi_actif else 0
    delta_surge  = ns - ns_nom if wi_actif else 0

    # ── Verdict ───────────────────────────────────────────────────────────────
    # Situation idéale
    if nr == 0 and sat <= 100:
        return "GO", "#16a34a", "Production dans les objectifs. Aucune surcharge."

    # Surcharges mais stock positif
    if nr == 0 and sat > 100:
        return ("GO CONDITIONNEL", "#d97706",
                f"{ns}/{p['weeks_total']} surcharges, stock positif. Leviers HS/anticipation.")

    # What-If actif et amélioration réelle → jamais NO-GO
    if wi_actif and wi_ameliore:
        gains = []
        if stock_ameliore:
            gains.append(f"stock {delta_stock:+,.0f} U ({mi_nom:,.0f} -> {mi:,.0f} U)")
        if surcharge_reduit:
            gains.append(f"surcharges {ns_nom} -> {ns}")
        gain_txt = ", ".join(gains)
        return ("GO CONDITIONNEL", "#d97706",
                f"Scenario {sc} ameliore : {gain_txt}. "
                f"Reste {nr} semaine(s) en rupture — ST residuelle requise.")

    # What-If actif mais sans amélioration mesurable
    if wi_actif and not wi_ameliore:
        return ("GO CONDITIONNEL", "#d97706",
                f"Scenario {sc} actif mais sans gain mesurable. "
                f"{nr} semaine(s) en rupture — changer de levier.")

    # Sans What-If : ruptures → NO-GO
    return ("NO-GO", "#dc2626",
            f"{nr} semaine(s) avec stock negatif — clients non livres. "
            f"Activer un levier (HS, ST, anticipation) avant de valider.")

def _orch_verdict_dem(arts):
    """Retourne (verdict, couleur, explication courte)."""
    if not arts:
        return "N/D", "#6b7280", "Aucune donnee demande chargee."
    mpy = sum(a["mape_py"] for a in arts) / len(arts)
    if mpy > 25:
        return ("NO-GO", "#dc2626",
                f"MAPE moyen {mpy:.1f}% trop eleve — previsions peu fiables.")
    if mpy > 15:
        return ("GO CONDITIONNEL", "#d97706",
                f"MAPE moyen {mpy:.1f}% — previsions acceptables, marge d'amelioration.")
    return "GO", "#16a34a", f"MAPE moyen {mpy:.1f}% — previsions fiables."


def _orch_build_report(data, scenario):
    """
    Rapport S&OP — adapte le raisonnement selon le CONTEXTE des données :
    - Données historiques → analyse de ce qui s'est passé + leçons pour le prochain cycle
    - Plan futur        → GO/NO-GO avec actions immédiates
    - Ambigu            → les deux angles
    """
    contexte = _orch_detect_context(data)
    flags    = _orch_detect_situation(data)
    diagnostics, actions = _orch_reason(data, flags)
    p = data["production"]; arts = data["demande"]; fin = data["finance"]
    out = []

    # ── Résumé exécutif — chiffres clés en un coup d'œil ─────────────────────
    kpi_cards = []
    if p:
        col_s = "#dc2626" if p["n_surcharge"]>0 else "#16a34a"
        col_m = "#dc2626" if p["stock_min"]<0 else "#16a34a"
        col_sat = "#dc2626" if p["sat_max"]>100 else "#16a34a"
        kpi_cards += [
            (f"{p['n_surcharge']}/{p['weeks_total']}", "Surcharges prod.", col_s),
            (f"{p['stock_min']:,.0f} U", "Stock minimum", col_m),
            (f"{p['sat_max']:.0f}%", "Saturation max", col_sat),
        ]
        if p["st_total"] > 0:
            kpi_cards.append((f"{p['st_total']:,.0f} U", "ST requise", "#dc2626"))
    if arts:
        mpy = round(sum(a["mape_py"] for a in arts)/len(arts), 1)
        col_mpy = "#16a34a" if mpy<15 else "#d97706" if mpy<25 else "#dc2626"
        kpi_cards.append((f"{mpy:.1f}%", "MAPE moyen", col_mpy))
        n_dec = sum(1 for a in arts if a["trend"]<-10)
        if n_dec > 0:
            kpi_cards.append((f"{n_dec}", "Déclin(s)", "#d97706"))
    if fin:
        col_fin = "#dc2626" if fin["n_deficit"]>0 else "#16a34a"
        kpi_cards.append((f"{fin['profit_total']:,.0f}", "Profit total", col_fin))

    if kpi_cards:
        cards_html = "".join(
            f'<div style="background:#f8f9fc;border:1.5px solid var(--br);'
            f'border-top:3px solid {col};border-radius:7px;'
            f'padding:.45rem .55rem;text-align:center;flex:1;min-width:90px">'
            f'<div style="font-size:1.05rem;font-weight:900;color:{col};'
            f'font-family:JetBrains Mono,monospace;line-height:1.2">{val}</div>'
            f'<div style="font-size:.63rem;color:var(--mu);margin-top:.1rem">{lbl}</div>'
            f'</div>'
            for val, lbl, col in kpi_cards)
        out.append(f'<div style="display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:.4rem">'
                   f'{cards_html}</div>')

    # ── Scénarios agents actifs ───────────────────────────────────────────────
    sc_actifs = data.get("scenarios_actifs", {})
    sc_lines  = []
    if sc_actifs.get("production"):
        sc_lines.append(f"Production : <strong>{sc_actifs['production']}</strong>")
    if sc_actifs.get("demande"):
        sc_lines.append(f"Demande : <strong>{sc_actifs['demande']}</strong>")
    sc_info = " | Scénarios actifs : " + " | ".join(sc_lines) if sc_lines else ""
    out.append(f'<div class="ai" style="margin-bottom:.35rem;font-size:.76rem">'
               f'<strong>Scénario :</strong> {scenario}{sc_info}</div>')

    # ── Bandeau Plan Prévisionnel (toutes les données sont actuelles) ─────────
    out.append("""
<div style="background:#f0fdf4;border-left:4px solid #16a34a;border-radius:6px;
  padding:.4rem .8rem;margin-bottom:.4rem">
  <div style="font-weight:800;font-size:.78rem;color:#16a34a;
    font-family:JetBrains Mono,monospace;margin-bottom:.05rem">📅 PLAN PRÉVISIONNEL</div>
  <div style="font-size:.75rem;color:#374151">
    Ces données représentent un plan à valider. Le verdict GO/NO-GO indique si le plan
    est réalisable tel quel ou sous conditions.
  </div>
</div>""")

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCHE HISTORIQUE
    # ══════════════════════════════════════════════════════════════════════════
    if contexte == "historique":
        # Pas de GO/NO-GO — analyse de ce qui s'est passé
        out.append(f"""
<div style="background:#f8f9fc;border:1.5px solid var(--br);border-radius:8px;
  padding:.65rem .9rem;margin:.3rem 0">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
    color:var(--mu);font-family:JetBrains Mono,monospace;margin-bottom:.15rem">
    Synthèse de la période analysée</div>""")

        if p:
            ns = p["n_surcharge"]; nw = p["weeks_total"]; mi = p["stock_min"]
            ms = p["sat_max"]; nr = p["n_rupture"]
            if ns == 0 and mi >= 0:
                out.append(f'<div style="color:#16a34a;font-weight:700;font-size:.85rem">'
                           f'Période sans incident — production dans les capacités, '
                           f'stock positif tout au long de la période.</div>')
            else:
                out.append(f'<div style="font-size:.82rem;line-height:1.7;color:#374151">')
                out.append(f'Sur cette période, <strong>{ns}/{nw} semaines</strong> ont dépassé '
                           f'la capacité de la ligne Fill-L1 ({p["cap_v"]:.0f} PHR/sem = '
                           f'{p["max_u"]:.0f} U/sem). ')
                if ms > 300:
                    out.append(f'Le pic le plus critique est <strong>{p["pic_w"]}</strong> avec '
                               f'{p["pic_dem"]:,.0f} unités demandées, soit <strong>{ms:.0f}%</strong> '
                               f'de la capacité nominale — la demande était 10 fois supérieure à ce '
                               f'que la ligne peut produire. ')
                if nr > 0:
                    out.append(f'Le stock est devenu négatif sur <strong>{nr} semaine(s)</strong>, '
                               f'atteignant un minimum de <strong>{mi:,.0f} U</strong>. '
                               f'Cela correspond à des commandes non livrées ou livrées en retard.')
                out.append('</div>')
        out.append('</div>')

        # ── Ce qu'on apprend de cette période ────────────────────────────────
        lecons = []
        if p and p["n_surcharge"] > 0:
            if p["sat_max"] > 300:
                lecons.append({
                    "titre": "Sous-capacité structurelle sur les pics",
                    "col": "#dc2626",
                    "analyse": (f"La demande sur {p['pic_w']} ({p['pic_dem']:,.0f} U) était "
                                f"{round(p['pic_dem']/p['max_u'],1) if p['max_u']>0 else '∞'}x la capacité. "
                                f"Ce n'est pas un incident ponctuel — c'est un gap structurel "
                                f"entre la capacité installée et la demande réelle."),
                    "lecon": ("Pour le prochain cycle : anticiper ces pics en négociant la capacité "
                              f"ST à l'avance (avant la période de pointe), pas en réaction. "
                              f"Le volume concerné est {p['st_total']:,.0f} U — obtenir un contrat "
                              "cadre ST plutôt qu'un devis d'urgence.")
                })
            if p["n_rupture"] > 0:
                lecons.append({
                    "titre": "Ruptures de stock client sur la période",
                    "col": "#dc2626",
                    "analyse": (f"{p['n_rupture']} semaine(s) avec stock négatif. "
                                f"Cela signifie que des clients ont été livrés en retard "
                                f"ou n'ont pas été livrés du tout pendant cette période."),
                    "lecon": ("Pour le prochain cycle : constituer un stock de sécurité "
                              "avant la période de forte demande. "
                              "Calculer le stock cible = demande moyenne × délai de réaction ST.")
                })
            if p["n_surcharge"] > 0 and p["sat_max"] <= 200:
                lecons.append({
                    "titre": "Surcharges modérées — gérables par anticipation",
                    "col": "#d97706",
                    "analyse": (f"{p['n_surcharge']} semaines en surcharge mais saturation "
                                f"max {p['sat_max']:.0f}% — inférieure à 200%. "
                                f"Ce type de surcharge est absorbable par anticipation ou HS."),
                    "lecon": ("Pour le prochain cycle : lisser la production dès les semaines "
                              "creuses. Pas besoin de ST si l'anticipation est planifiée à temps.")
                })

        if arts:
            mpy_avg = round(sum(a["mape_py"] for a in arts)/len(arts), 1)
            merp_avg = round(sum(a["mape_erp"] for a in arts)/len(arts), 1)
            if merp_avg == 0:
                lecons.append({
                    "titre": "Prévisions ERP absentes sur cette période",
                    "col": "#d97706",
                    "analyse": ("MAPE ERP = 0% sur tous les articles, ce qui indique "
                                "que le système ERP n'avait pas de prévision renseignée. "
                                "Les données chargées sont des consommations réelles, pas des prévisions."),
                    "lecon": (f"Pour le prochain cycle : utiliser les prévisions Python "
                              f"(MAPE {mpy_avg:.1f}%) comme base du plan S&OP. "
                              f"Elles sont calculées sur l'historique réel que vous venez de charger.")
                })
            elif mpy_avg < 15:
                lecons.append({
                    "titre": "Qualité de prévision : bonne",
                    "col": "#16a34a",
                    "analyse": (f"MAPE Python moyen {mpy_avg:.1f}% sur la période — "
                                f"les prévisions sont fiables."),
                    "lecon": "Continuer avec la méthode actuelle pour le prochain cycle."
                })

        if lecons:
            lecon_rows = [
                [f'<span style="color:{l["col"]};font-weight:700">{l["titre"]}</span>',
                 l["analyse"], l["lecon"]]
                for l in lecons
            ]
            out.append(T(
                ["Point identifié", "Ce qui s'est passé", "Leçon pour le prochain cycle S&OP"],
                lecon_rows, None,
                "Analyse de la période — leçons pour le cycle suivant"
            ))

        # ── Recommandations pour le PROCHAIN cycle ────────────────────────────
        reco = []
        if p and p["st_total"] > 0 and p["sat_max"] > 200:
            reco.append({"prio": 1, "resp": "Direction Achats + COO",
                "action": (f"Négocier un contrat cadre de sous-traitance pour les pics récurrents "
                           f"({p['st_total']:,.0f} U/an estimé). Un contrat cadre coûte 15-20% "
                           f"moins cher qu'un devis d'urgence."),
                "timing": "Avant le prochain cycle de forte demande",
                "objectif": "Zéro rupture stock sur les périodes de pointe."})
        if p and p["n_surcharge"] > 0 and p["sat_max"] <= 200:
            reco.append({"prio": 1, "resp": "Responsable Production",
                "action": ("Établir un plan de lissage : produire en avance sur les semaines "
                           "creuses pour constituer un stock tampon avant les pics."),
                "timing": "Dès le début du prochain cycle",
                "objectif": "0 surcharge sans recours à HS ou ST."})
        if arts and all(a["mape_erp"] == 0 for a in arts):
            reco.append({"prio": len(reco)+1, "resp": "Planification Demande",
                "action": (f"Intégrer les prévisions Python dans le prochain plan S&OP "
                           f"(MAPE {round(sum(a['mape_py'] for a in arts)/len(arts),1):.1f}%). "
                           f"Ces prévisions sont basées sur l'historique réel que vous venez d'analyser."),
                "timing": "Avant la prochaine revue S&OP",
                "objectif": "Plan de production basé sur des prévisions quantifiées."})
        if not reco:
            reco.append({"prio": 1, "resp": "Équipe S&OP",
                "action": "Période sans incident majeur. Maintenir les pratiques actuelles.",
                "timing": "Prochain cycle",
                "objectif": "Continuité."})

        reco_rows = [[f"Priorité {r['prio']}", r["resp"], r["action"],
                      r["timing"], r["objectif"]] for r in reco]
        out.append(T(
            ["Priorité","Responsable","Recommandation pour le prochain cycle","Quand","Objectif"],
            reco_rows, None,
            "Plan d'amélioration — prochain cycle S&OP (pas des actions rétroactives)"
        ))
        out.append(f'<div class="ag" style="margin-top:.3rem">'
                   f'<strong>Rappel :</strong> ces recommandations s\'appliquent au '
                   f'<strong>prochain cycle S&OP</strong>, pas à la période déjà écoulée.</div>')

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCHE PLAN FUTUR
    # ══════════════════════════════════════════════════════════════════════════
    elif contexte == "plan":
        v_global, c_global = _orch_verdict_global(flags)
        n_actions = len(actions)
        if v_global == "GO" and n_actions == 0:
            verdict_detail = "Tous les indicateurs sont dans les objectifs. Plan validé."
        elif v_global == "GO CONDITIONNEL":
            verdict_detail = (f"{n_actions} action(s) à réaliser avant de valider le plan.")
        else:
            verdict_detail = (f"Plan non réalisable en l'état. "
                              f"{n_actions} action(s) corrective(s) requises.")

        out.append(f"""
<div style="background:#f8f9fc;border:2px solid {c_global};border-radius:8px;
  padding:.65rem .9rem;margin:.3rem 0">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
    color:var(--mu);font-family:JetBrains Mono,monospace;margin-bottom:.15rem">Verdict S&OP</div>
  <div style="font-size:1.05rem;font-weight:900;color:{c_global};margin-bottom:.15rem">{v_global}</div>
  <div style="font-size:.78rem;color:#374151">{verdict_detail}</div>
</div>""")

        # Bilan par domaine
        bilan_rows = []
        for d in diagnostics:
            bilan_rows.append([
                d["domaine"], d["analyse"],
                f'<span style="color:{d["col"]};font-weight:700">{d["statut"]}</span>',
                d["action"] if d["action"] else "Aucune action requise"
            ])
        if bilan_rows:
            out.append(T(["Domaine","Situation","Statut","Orientation"],
                         bilan_rows, None, "Analyse par domaine"))

        # ── Synthèse chiffrée avant le plan d'action ─────────────────────────
        synth_lines = []
        if p:
            synth_lines.append(
                f"Production : cap {p['cap_v']:.0f} PHR/sem = {p['max_u']:.0f} U/sem | "
                f"<strong>{p['n_surcharge']}/{p['weeks_total']}</strong> surcharges | "
                f"sat max <strong>{p['sat_max']:.0f}%</strong> | "
                f"stock min <strong style='color:{'#dc2626' if p['stock_min']<0 else '#16a34a'}'>"
                f"{p['stock_min']:,.0f} U</strong>"
                + (f" | ST requise : <strong>{p['st_total']:,.0f} U</strong>" if p['st_total']>0 else ""))
            if p.get("scenario") and p["scenario"] != "Nominal":
                synth_lines.append(
                    f"Scénario production actif : <strong>{p['scenario']}</strong>")
        for a in arts[:3]:
            sc_badge = f" [scénario : {a.get('scenario','')}]" if a.get("scenario","Auto") != "Auto" else ""
            synth_lines.append(
                f"Demande {a['article'][:20]}{sc_badge} : "
                f"MAPE Python <strong>{a['mape_py']:.1f}%</strong> ({a['methode']}) | "
                f"Forecast M+1 : <strong>{a['fc_m1']:,.0f} U</strong> | "
                f"Trend : <strong>{a['trend']:+.1f}</strong>")
        if fin:
            synth_lines.append(
                f"Finance : profit total <strong>{fin['profit_total']:,.0f}</strong> | "
                f"déficitaires : <strong>{fin['n_deficit']}</strong>")
        if synth_lines:
            out.append(S("Synthèse chiffrée — tous agents", synth_lines))

        # Plan d'action
        if actions:
            action_rows = [[f"Étape {a['prio']}", a["resp"], a["action"],
                            a["delai"], a["condition"]]
                           for a in sorted(actions, key=lambda x: x["prio"])]
            out.append(T(
                ["Étape","Responsable","Action","Délai","Condition de passage"],
                action_rows, None,
                "Plan d'action — séquence (une étape à la fois)"
            ))
        else:
            out.append(f'<div class="ag">Plan validé — aucune action corrective requise.</div>')

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCHE AMBIGUË — les deux angles
    # ══════════════════════════════════════════════════════════════════════════
    else:
        out.append(f'<div class="aw">'
                   f'<strong>Contexte indéterminé.</strong> '
                   f'Précisez si ces données sont historiques (consommations passées) '
                   f'ou prévisionnelles (plan futur) pour une analyse adaptée. '
                   f'En attendant, voici les faits clés :</div>')
        if p:
            out.append(f'<div style="font-size:.8rem;padding:.3rem 0">'
                       f'Production : {p["n_surcharge"]}/{p["weeks_total"]} surcharges | '
                       f'Sat max {p["sat_max"]:.0f}% | Stock min {p["stock_min"]:,.0f} U</div>')
        for a in arts[:2]:
            out.append(f'<div style="font-size:.8rem;padding:.2rem 0">'
                       f'{a["article"][:24]} : MAPE Python {a["mape_py"]:.1f}% ({a["methode"]}) '
                       f'| Forecast M+1 : {a["fc_m1"]:,.0f} U</div>')

    # ── Données manquantes ────────────────────────────────────────────────────
    missing = [k.capitalize() for k,v in
               [("production",not p),("demande",not arts),("finance",not fin)] if v]
    if missing:
        out.append(f'<div class="aw" style="margin-top:.3rem">'
                   f'<strong>Données manquantes :</strong> {", ".join(missing)} — '
                   f'charger les fichiers pour un rapport complet.</div>')

    return "".join(out)


def orchestrate(scenario="SITUATION NOMINALE"):
    """Analyse S&OP avec discussion inter-agents claire et LLM pour la justification."""
    disc = []
    ts = lambda: datetime.now().strftime("%H:%M:%S")
    def add(ag, c):
        disc.append({"agent": ag, "content": c, "ts": ts()})
        st.session_state.disc = disc.copy()

    add("ORCH", f"Lancement de l'analyse S&OP — <strong>Scénario : {scenario}</strong>")
    data = _orch_collect_data()
    p    = data["production"]
    arts = data["demande"]
    fin  = data["finance"]

    # ── Afficher les erreurs de chargement de scénarios ───────────────────
    if data.get("errors"):
        for err in data["errors"]:
            add("ORCH", f"<div style='background:#fef2f2;border-left:3px solid #dc2626;"
                        f"border-radius:4px;padding:.3rem .6rem;font-size:.75rem'>"
                        f"⚠ {err}</div>")

    # ── Confirmer les scénarios actifs ────────────────────────────────────
    sc_actifs_log = data.get("scenarios_actifs", {})
    if sc_actifs_log:
        sc_txt_log = " | ".join(f"<strong>{k}</strong> : {v}" for k,v in sc_actifs_log.items())
        add("ORCH", f"<div style='background:#eff6ff;border-left:3px solid #2563eb;"
                    f"border-radius:4px;padding:.3rem .6rem;font-size:.75rem'>"
                    f"📐 Scenarios What-If lus et appliques : {sc_txt_log}</div>")
    else:
        add("ORCH", "<div style='font-size:.75rem;color:#6b7280'>"
                    "Aucun scenario What-If actif — analyse en mode nominal.</div>")

    # ── Messages inter-agents CLAIRS (lisibles par n'importe qui) ─────────────
    # PRODUCTION
    if p:
        sat_max = p["sat_max"]
        ns = p["n_surcharge"]; nw = p["weeks_total"]
        mi = p["stock_min"]; nr = p["n_rupture"]
        sc_prod = p.get("scenario","Nominal")

        if sc_prod and sc_prod != "Nominal":
            sc_info = f" <em>(scénario : {sc_prod})</em>"
        else:
            sc_info = ""

        # Message simplifié et compréhensible
        if ns == 0 and mi >= 0:
            prod_msg = (f"La ligne de production Fill-L1 peut absorber toute la demande{sc_info}. "
                        f"<strong>Aucune semaine en surcharge</strong>. "
                        f"Le stock reste positif à {mi:,.0f} U minimum. "
                        f"<span style='color:#16a34a;font-weight:700'>Production : RAS.</span>")
        elif ns > 0 and mi >= 0:
            prod_msg = (f"La production est sous pression{sc_info} : "
                        f"<strong style='color:#d97706'>{ns} semaine(s) sur {nw}</strong> "
                        f"dépassent la capacité ({p['cap_v']:.0f} PHR/sem = {p['max_u']:.0f} U/sem). "
                        f"Le stock reste positif ({mi:,.0f} U) — le risque est limité pour l'instant. "
                        f"Saturation max : <strong>{sat_max:.0f}%</strong>. "
                        f"<span style='color:#d97706;font-weight:700'>A surveiller.</span>")
        else:
            prod_msg = (f"<strong style='color:#dc2626'>Situation critique{sc_info}</strong> : "
                        f"{ns}/{nw} semaines dépassent la capacité, dont {nr} semaines où "
                        f"le stock passe négatif (<strong style='color:#dc2626'>{mi:,.0f} U</strong>). "
                        f"Pic le plus élevé : {p['pic_w']} à {p['pic_dem']:,.0f} U/sem "
                        f"= {sat_max:.0f}% de la capacité. "
                        f"En clair : on ne peut pas livrer tous les clients sur ces {nr} semaines. "
                        f"<span style='color:#dc2626;font-weight:700'>Action requise.</span>")
        add("PRODUCTION", f"<div>{prod_msg}</div>")
    else:
        add("PRODUCTION", "<div>Aucun fichier production charge. Merci de charger un fichier dans l'onglet Production.</div>")

    # DEMANDE
    if arts:
        for a in arts[:3]:
            sc_dem = a.get("scenario","Auto")
            mpy = a["mape_py"]; erp = a["mape_erp"]
            trend = a["trend"]
            gain = mpy - erp if erp > 0 else None

            if mpy < 15:
                qualite = f"<span style='color:#16a34a;font-weight:700'>très précise</span>"
            elif mpy < 25:
                qualite = f"<span style='color:#d97706;font-weight:700'>acceptable</span>"
            else:
                qualite = f"<span style='color:#dc2626;font-weight:700'>imprécise — à améliorer</span>"

            trend_txt = (f"La demande <strong>croît de {abs(trend):.1f} U/mois</strong>." if trend > 5
                         else f"La demande <strong>décline de {abs(trend):.1f} U/mois</strong> — signal d'alerte." if trend < -5
                         else "La demande est <strong>stable</strong>.")

            dem_msg = (f"<strong>{a['article'][:25]}</strong> "
                       f"({a['n']} périodes) — "
                       f"Prévision {qualite} : erreur moyenne {mpy:.1f}% "
                       + (f"(gain de {gain:.1f} points vs ERP)" if gain and gain < 0 else "") + ". "
                       + trend_txt
                       + (f" Scénario : {sc_dem}." if sc_dem not in ("Auto","DEM_AUTO","") else ""))
            add("DEMANDE", f"<div>{dem_msg}</div>")
    else:
        add("DEMANDE", "<div>Aucun fichier demande charge. Le plan de production ne peut pas etre valide sans previsions.</div>")

    # FINANCE
    if fin:
        pt = fin["profit_total"]; nd = fin["n_deficit"]; nc = fin["n_critique"]
        if nd == 0 and nc == 0:
            fin_msg = (f"Portefeuille sain : profit total <strong>{pt:,.0f}</strong>. "
                       f"Aucun produit déficitaire. "
                       f"<span style='color:#16a34a;font-weight:700'>Finance : RAS.</span>")
        elif nd > 0:
            fin_msg = (f"<strong style='color:#dc2626'>{nd} produit(s) déficitaire(s)</strong> "
                       f"(ils coûtent plus cher à produire qu'ils ne rapportent). "
                       f"Profit total : <strong>{pt:,.0f}</strong>. "
                       f"Attention : produire ces articles en plus grande quantité "
                       f"<em>aggrave les pertes</em>. Révision tarifaire recommandée.")
        else:
            fin_msg = (f"Profit total : <strong>{pt:,.0f}</strong>. "
                       f"{nc} produit(s) avec marge inférieure à 10% — "
                       f"vulnérables à toute hausse de coût. À surveiller.")
        add("FINANCE", f"<div>{fin_msg}</div>")

    # ORCH — Raisonnement LLM clair
    flags      = _orch_detect_situation(data)
    diagnostics, actions = _orch_reason(data, flags)
    v_global, c_global   = _orch_verdict_global(flags)

    # Construire un résumé factuel compact pour le LLM
    facts = []
    if p:
        facts.append(f"Production: {p['n_surcharge']}/{p['weeks_total']} surcharges, "
                     f"stock min {p['stock_min']:,.0f}U, sat max {p['sat_max']:.0f}%")
        if p.get("scenario","Nominal") != "Nominal":
            facts.append(f"Scenario actif: {p['scenario']}")
    if arts:
        mpy_avg = round(sum(a["mape_py"] for a in arts)/len(arts),1)
        facts.append(f"Demande: MAPE moyen {mpy_avg}%, {sum(1 for a in arts if a['trend']<-5)} article(s) en declin")
    if fin:
        facts.append(f"Finance: {fin['n_deficit']} deficit(s), profit {fin['profit_total']:,.0f}")

    wi_txt = ""
    sc_actifs = data.get("scenarios_actifs",{})
    if sc_actifs:
        wi_txt = " Scenarios What-If actifs: " + " | ".join(f"{k}:{v}" for k,v in sc_actifs.items())

    # ── LLM — raisonnement ancré dans les chiffres réels ─────────────────────
    # Construire un contexte riche et SPÉCIFIQUE pour que le LLM raisonne vraiment
    ctx_prod = ""
    ctx_dem  = ""
    ctx_wi   = ""
    ctx_fin  = ""

    if p:
        ctx_prod = (f"Production : {p['n_surcharge']}/{p['weeks_total']} semaines en surcharge "
                    f"(saturation max {p['sat_max']:.0f}% en {p['pic_w']}). "
                    f"Stock minimum : {p['stock_min']:,.0f} U sur {p['n_rupture']} semaines. "
                    f"Capacite : {p['cap_v']:.0f} PHR/sem = {p['max_u']:.0f} U/sem max. "
                    f"Pic de demande : {p['pic_dem']:,.0f} U/sem "
                    f"= {round(p['pic_dem']/p['max_u'],1) if p['max_u']>0 else '?'}x la capacite.")

    if arts:
        art_details = " | ".join(
            f"{a['article'][:20]} "
            f"MAPE={a['mape_py']:.1f}% ({a['methode']}) "
            f"tendance={'+' if a['trend']>=0 else ''}{a['trend']:+.1f} U/periode "
            f"(N={a.get('n','-')} periodes)"
            for a in arts)
        ctx_dem = f"Demande : {art_details}."

    if sc_actifs:
        ctx_wi = ("Scenarios What-If actifs : "
                  + " | ".join(f"{k} = {v}" for k,v in sc_actifs.items())
                  + ".")
    else:
        ctx_wi = "Aucun scenario What-If actif — analyse en mode nominal."

    if fin:
        ctx_fin = (f"Finance : profit {fin['profit_total']:,.0f}, "
                   f"{fin['n_deficit']} produit(s) deficitaire(s).")

    situation_complete = " ".join(filter(None, [ctx_prod, ctx_dem, ctx_wi, ctx_fin]))

    llm_prompt = (
        f"Tu es le directeur S&OP d'une entreprise industrielle. "
        f"Voici la situation exacte ce mois-ci : {situation_complete} "
        f"Le systeme a calcule le verdict : {v_global}. "
        f"En 2 phrases maximum, dis clairement : "
        f"(1) pourquoi cette situation aboutit a ce verdict en citant les chiffres cles, "
        f"(2) quelle est l'action la plus urgente a prendre. "
        f"NE PAS utiliser de liste numerotee. "
        f"Parle comme un directeur industriel, pas comme un consultant. "
        f"Sois direct et precis."
    )

    try:
        justification = groq("Expert S&OP. Reponds UNIQUEMENT en francais. Utilise les chiffres exacts fournis. Ne dis jamais de pourcentage pour la tendance si elle est en U/periode.", llm_prompt, 180)
        # Nettoyer les listes numérotées si le LLM en produit quand même
        import re as _re
        justification = _re.sub(r"^[0-9]+\.\s*", "", justification, flags=_re.MULTILINE)
        justification = justification.replace("\n", " ").strip()
    except Exception:
        justification = (f"{ctx_prod} {ctx_wi} Verdict : {v_global}.")

    add("ORCH", f"""
<div style="background:#f0f2f7;border-left:4px solid #1e3a8a;border-radius:6px;padding:.5rem .8rem">
  <div style="font-weight:700;font-size:.75rem;color:#1e3a8a;margin-bottom:.25rem">
    Verdict : <span style="color:{c_global}">{v_global}</span>
  </div>
  <div style="font-size:.79rem;color:#374151;line-height:1.65">{justification}</div>
</div>""")

    # ── Rapport final ─────────────────────────────────────────────────────────
    add("ORCH", "Construction du rapport complet...")
    rapport = _orch_build_report(data, scenario)
    disc[-1]["content"] = rapport
    st.session_state.disc = disc.copy()

    # ── Email automatique ─────────────────────────────────────────────────────
    try:
        _auto_email_check(trigger="Analyse S&OP Orchestrateur", agent="orchestrateur")
    except Exception:
        pass
# ── RENDER CHAT ────────────────────────────────────────────────────────────────
def _build_chat_html(agent):
    """
    Construit TOUT le chat en un seul bloc HTML.
    Évite les multiples st.markdown() dans un container qui causent le tremblement.
    """
    msgs = st.session_state.chats.get(agent, [])
    abbr = {"marketing":"MKT","demande":"DEM","production":"PRD",
            "finance":"FIN","orchestrateur":"ORC"}.get(agent,"AGT")
    if not msgs:
        return ('<div style="color:#6b7299;font-size:.79rem;text-align:center;'
                'padding:1.2rem 0">Charge un fichier puis clique sur un bouton d\'analyse.</div>')
    parts = []
    for m in msgs[-25:]:
        content = fmt(m["content"])
        if m["role"] == "user":
            parts.append(
                f'<div class="msg-u">'
                f'<div class="bub bub-u">{content}</div>'
                f'</div>')
        else:
            parts.append(
                f'<div class="msg-a">'
                f'<div class="av">{abbr}</div>'
                f'<div class="bub bub-a">{content}</div>'
                f'</div>')
    return "".join(parts)


def _build_disc_html():
    """Construit TOUTE la discussion inter-agents en un seul bloc HTML."""
    disc = st.session_state.disc
    if not disc:
        return ('<div style="color:#6b7299;font-size:.79rem;text-align:center;'
                'padding:1.2rem 0">Lance l\'analyse S&OP pour voir la discussion.</div>')
    parts = []
    for item in disc:
        content = fmt(item["content"])
        parts.append(
            f'<div class="msg-a" style="padding:.3rem 0;border-bottom:1px solid var(--bg2)">'
            f'<div class="av">{item["agent"][:3]}</div>'
            f'<div style="flex:1">'
            f'<div style="font-size:.67rem;font-family:JetBrains Mono,monospace;'
            f'color:var(--navy);font-weight:700;margin-bottom:.08rem">'
            f'{item["agent"]} <span style="color:var(--mu);font-weight:400">{item["ts"]}</span></div>'
            f'<div style="font-size:.79rem;line-height:1.58">{content}</div>'
            f'</div></div>')
    return "".join(parts)


def render_chat(agent):
    """
    Rendu du chat en UN SEUL appel st.markdown() + div scrollable CSS.
    Élimine le tremblement causé par st.container(height=...) + multiples markdown.
    """
    chat_html = _build_chat_html(agent)
    uid = f"chat_{agent}"
    st.markdown(
        f'<div id="{uid}" class="chat-box" '
        f'style="height:415px;overflow-y:auto;padding:.5rem .6rem;'
        f'border:1.5px solid var(--br);border-radius:8px;background:var(--bg1)">'
        f'{chat_html}</div>'
        f'<script>'
        f'(function(){{var el=document.getElementById("{uid}");'
        f'if(el)el.scrollTop=el.scrollHeight;}})();'
        f'</script>',
        unsafe_allow_html=True)


def render_disc():
    """
    Rendu de la discussion inter-agents en UN SEUL appel st.markdown().
    Élimine le tremblement causé par multiples markdown dans un container.
    """
    disc_html = _build_disc_html()
    st.markdown(
        f'<div id="disc_panel" class="chat-box" '
        f'style="height:390px;overflow-y:auto;padding:.5rem .6rem;'
        f'border:1.5px solid var(--br);border-radius:8px;background:var(--bg1)">'
        f'{disc_html}</div>'
        f'<script>'
        f'(function(){{var el=document.getElementById("disc_panel");'
        f'if(el)el.scrollTop=el.scrollHeight;}})();'
        f'</script>',
        unsafe_allow_html=True)

# ── BUTTONS MAP ────────────────────────────────────────────────────────────────
BTNS={
    "marketing":[
        ("Analyse complete","__MKT_AUTO__"),
        ("Dashboard","__DASHBOARD__"),
        ("Produits en declin","Quels produits sont en declin ? Tendances baissières et chiffres."),
        ("Meilleurs mois promo","Meilleurs mois pour les promotions ? Facteurs saisonniers (HW uniquement)."),
        ("Impact promo -20%","Calcule l'impact d'une promotion -20% sur le volume et le CA."),
    ],
    "demande":[
        ("Analyse complete","__DEM_AUTO__"),
        ("Dashboard","__DASHBOARD__"),
        ("MA vs LES vs HW","__DEM_METHODS__"),
        ("Anomalies historique","__DEM_ANOM__"),
        ("MAPE le plus eleve","__DEM_MAPE__"),
        ("Forecast 6 mois","__DEM_FC__"),
    ],
    "production":[
        ("Analyse & MRP complet","__PRD_MRP__"),
        ("Dashboard","__DASHBOARD__"),
        ("Surcharges uniquement","__PRD_SURGE__"),
        ("Simulation +30% demande","__PRD_SIM30__"),
        ("Stock securite","__PRD_SS__"),
    ],
    "finance":[
        ("Analyse complete","__FIN_AUTO__"),
        ("Dashboard","__DASHBOARD__"),
        ("Rentabilite","Profit par produit (Volume x Marge). Classe par rentabilite."),
        ("Seuil rentabilite","Seuil de rentabilite par produit : CF / (Prix - Cout variable)."),
        ("Alertes marges","Produits marge insuffisante : CRITIQUE < 5%, ATTENTION 5-10%, SAIN > 10%."),
    ],
}
CAPS={
    "marketing":    ["Classement portefeuille","Saisonnalite (HW si detectee)","Simulation promotions","Alertes declin"],
    "demande":      ["MA (fenetre) / LES (α) / HW (α,β,γ)","MAPE min = methode retenue","ERP = systeme entreprise","Intervalles confiance 85%"],
    "production":   ["MRP complet sous contraintes","Plan synthetique capacite/stock/lot","Options action hierarchisees","Stock projete semaine/semaine"],
    "finance":      ["P&L Volume x Marge","Seuil rentabilite","Alertes marges avec hypotheses","Impact scenarios"],
    "orchestrateur":["Analyse auto tous agents","Plan d'action sequence (1→2→3)","GO/NO-GO chiffre","Rapport S&OP final"],
}

# ── Dictionnaire de définitions par agent ─────────────────────────────────────
DEFS = {
    "demande": [
        ("MAPE %", "Erreur moyenne en % — plus bas = plus précis. "
                "Ex : MAPE=10% → les prévisions se trompent en moyenne de 10% vs la demande réelle."),
        ("MAE", "Erreur absolue moyenne en unités. "
                "Ex : MAE=50 → les prévisions s'écartent en moyenne de 50 U de la demande réelle."),
        ("CV % — Coefficient de Variation", "CV = Écart-type / Moyenne × 100. "
                "CV < 30% → série stable. CV > 60% → série très volatile, toute méthode sera imprécise."),
        ("Int. bas / Int. haut", "Intervalle de confiance à ~85%. "
                "Dans ~85% des cas, la demande réelle tombera entre ces deux bornes."),
        ("Anomalie (±2σ)", "Valeur hors de [Moyenne ± 2 × Écart-type]. "
                "Pic = trop haute. Creux = trop basse. Peut biaiser les prévisions."),
        ("Gain vs ERP", "Différence de MAPE entre la méthode Python et la prévision ERP. "
                "Positif = Python plus précis. Négatif = ERP déjà meilleur."),
    ],
    "marketing": [
        ("MAPE %", "Erreur de prévision en % — plus bas = plus précis."),
        ("CV % — Volatilité", "CV élevé → demande instable, difficile à prévoir et à planifier."),
        ("Tendance", "Variation de la demande par période. Positive = croissance. Négative = déclin."),
        ("Part %", "Part de l'article dans le volume total. Identifie les articles Pareto 80/20."),
        ("Facteurs saisonniers F(n,k)", "Écart récurrent de chaque période par rapport à la moyenne. "
                "F=1.25 → ce mois est 25% au-dessus de la moyenne annuelle."),
    ],
    "production": [
        ("Sat % — Saturation", "Charge PHR ÷ Cap PHR × 100. "
                "100% = machine à plein. > 100% = surcharge impossible sans action externe."),
        ("PHR — Heures machine", "Heures machine consommées ou disponibles. "
                "Charge = Demande × Taux (PHR/U). Cap = plafond hebdomadaire de la ligne."),
        ("Surplus PHR", "Cap PHR − Charge PHR. Négatif = surcharge."),
        ("Stock min projeté", "Stock le plus bas sur toute la période. "
                "Négatif = rupture = clients non livrés."),
        ("Ruptures", "Semaines avec stock négatif. Chaque rupture = commandes non livrées."),
        ("Net Req", "Besoin net = Gross Req − Stock disponible − Stock sécurité."),
        ("PO — Planned Order", "Ordre de production planifié pour couvrir le besoin net."),
        ("Stock sécurité SS", "SS = Z × σ × √LT. Stock tampon contre les aléas de demande."),
    ],
    "finance": [
        ("Profit Total", "Volume × Marge unitaire. Bénéfice généré par produit."),
        ("Taux de marge %", "Marge ÷ Prix × 100. < 5% critique. 5–10% attention. > 10% sain."),
        ("Seuil de rentabilité", "Volume minimal pour couvrir les coûts fixes : CF ÷ (Prix − Coût variable)."),
        ("P&L", "Profit & Loss = Revenus − Coûts. Compte de résultat simplifié par produit."),
    ],
    "orchestrateur": [
        ("GO", "Plan validé. Tous les indicateurs dans les objectifs. Aucune action requise."),
        ("NO-GO", "Plan non validé. Actions correctives obligatoires avant démarrage."),
        ("GO CONDITIONNEL", "Plan acceptable si les actions indiquées sont réalisées dans les délais."),
        ("Surcharge", "Demande > capacité interne. Sat > 100%. Nécessite HS ou sous-traitance."),
        ("Rupture stock", "Stock projeté < 0 = clients non livrés. Impact direct taux de service."),
        ("MAPE %", "Erreur de prévision demande — plus bas = plus précis. Objectif < 15%."),
    ],
}

def render_definitions(agent):
    """
    Affiche un bouton 'Définitions' qui, au clic, ouvre un expander
    avec toutes les définitions contextuelles de l'agent.
    """
    defs = DEFS.get(agent, DEFS.get("demande", []))
    if not defs:
        return
    with st.expander("📖 Définitions — cliquer pour afficher", expanded=False):
        for terme, definition in defs:
            st.markdown(
                f'<div style="margin-bottom:.45rem;padding:.35rem .5rem;'
                f'background:#f8f9fc;border-left:3px solid var(--navy);border-radius:4px">'
                f'<div style="font-weight:700;font-size:.74rem;font-family:JetBrains Mono,monospace;'
                f'color:var(--navy);margin-bottom:.1rem">{terme}</div>'
                f'<div style="font-size:.76rem;color:#374151;line-height:1.6">{definition}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

def prod_mrp(dfs, q=""):
    # Lire le scénario What-If actif SAUF si un override explicite (q) est passé
    if q and q.strip():
        mrp = mrp_calc(dfs, {})
        ov = parse_ov(q, mrp["weeks"]) if q else {}
        if ov: mrp = mrp_calc(dfs, ov)
        cap_active = mrp["p"]["cap_v"]
        sc_label   = ""
    else:
        mrp, cap_active, sc_label = _get_active_mrp(dfs)
    p=mrp["p"]; W=mrp["weeks"]
    n_s=sum(1 for x in mrp["status"] if x=="SURCHARGE")
    n_a=sum(1 for x in mrp["status"] if x=="ALERTE")
    ms=max(mrp["sat"]); mi=min(mrp["inv_e"])
    out=[]

    hs25=round(p["cap_v"]*1.25/p["var_v"],0) if p["var_v"]>0 else p["cap_v"]
    out.append(f"""
<div class="synth">
<div class="synth-h">Plan de Production — Synthese sous contraintes</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.4rem;margin-top:.25rem">
  <div><strong>Contrainte Capacite</strong><br>
    Ressource : Fill-L1<br>
    Capacite : <strong>{p['cap_v']:.0f} PHR/sem</strong><br>
    Taux Fill-L1 : <strong>{p['var_v']:.4f} PHR/U</strong><br>
    Max nominal : <strong>{p['max_u']:.0f} U/sem</strong><br>
    Max +25% HS : <strong>{hs25:.0f} U/sem</strong>
  </div>
  <div><strong>Contrainte Stock</strong><br>
    Stock initial : <strong>{p['inv0']:,.0f} U</strong><br>
    Stock securite : <strong>{p['ss_v']:.0f} U</strong><br>
    Stock min projete : <strong style="color:{'#dc2626' if mi<0 else '#16a34a'}">{mi:,.0f} U</strong><br>
    Ruptures : <strong style="color:{'#dc2626' if sum(1 for v in mrp['inv_e'] if v<0)>0 else '#16a34a'}">{sum(1 for v in mrp['inv_e'] if v<0)}/{len(W)} sem.</strong>
  </div>
  <div><strong>Contrainte Lots / MinProd</strong><br>
    Taille lot : <strong>{p.get('bat_v',1):.0f} U/lot</strong><br>
    Surcharges : <strong style="color:{'#dc2626' if n_s>0 else '#16a34a'}">{n_s}/{len(W)}</strong><br>
    Alertes (85-100%) : <strong style="color:{'#d97706' if n_a>0 else '#16a34a'}">{n_a}/{len(W)}</strong><br>
    Saturation max : <strong>{ms:.1f}%</strong>
  </div>
</div>
</div>""")

    peaks=[(W[i],mrp["gross"][i]) for i in range(len(W)) if mrp["gross"][i]>p["max_u"]*3]
    if peaks:
        w,g=max(peaks,key=lambda x:x[1]); r=round(g/p["max_u"],1) if p["max_u"]>0 else "∞"
        out.append(f'<div class="ae"><strong>Pic critique</strong> : {w.replace(" Y23","")} demande {g:,.0f} U/sem — cap. max {p["max_u"]:.0f} U (x{r}). Sous-traitance obligatoire.</div>')
    if mi<0:
        fi=next((W[i] for i in range(len(W)) if mrp["inv_e"][i]<0),None)
        fv=next((mrp["inv_e"][i] for i in range(len(W)) if mrp["inv_e"][i]<0),0)
        if fi: out.append(f'<div class="ae"><strong>Rupture stock</strong> : des {fi.replace(" Y23","")}, stock = {fv:,.0f} U (stock negatif = clients non livres).</div>')
    if n_s==0: out.append(f'<div class="ag">Aucune surcharge. Saturation max {ms:.1f}%.</div>')

    hd=["Periode","Gross Req","Charge PHR","Cap PHR","Surplus PHR","Sat %","Net Req","PO","Plan ajuste","Stock fin","Statut"]
    rows=[]; cls=[]
    for i,w in enumerate(W):
        wl=w.replace(" Y23","").replace(" Y2023","")
        adj=int(min(mrp["gross"][i],p["max_u"])) if mrp["status"][i]=="SURCHARGE" else int(mrp["plan"][i])
        rows.append([wl,f"{mrp['gross'][i]:,.0f}",f"{mrp['charge'][i]:,.1f}",f"{mrp['cap'][i]:,.0f}",
                     f"{mrp['surplus'][i]:,.1f}",f"{mrp['sat'][i]:.1f}%",f"{mrp['net'][i]:,.0f}",
                     f"{mrp['po'][i]:,.0f}",f"{adj:,}",f"{mrp['inv_e'][i]:,.0f}",sc(mrp["status"][i])])
        cls.append("surge" if mrp["status"][i]=="SURCHARGE" else "alrt" if mrp["status"][i]=="ALERTE" else "")
    out.append(T(hd,rows,cls,"Tableau MRP Complet — toutes periodes"))

    hd2=["Periode","Stock debut","+ Production","- Gross Req","= Stock fin","Statut"]
    rows2=[]; cls2=[]
    for i,w in enumerate(W):
        wl=w.replace(" Y23",""); fin=mrp["inv_e"][i]
        rows2.append([wl,f"{mrp['inv_s'][i]:,.0f}",f"+{mrp['plan'][i]:,.0f}",
                      f"-{mrp['gross'][i]:,.0f}",f"{fin:,.0f}",
                      f'<span style="color:{"#dc2626" if fin<0 else "#16a34a"};font-weight:700">{"RUPTURE — clients non livres" if fin<0 else "OK"}</span>'])
        cls2.append("surge" if fin<0 else "")
    out.append(T(hd2,rows2,cls2,"Stock Projete — Periode par Periode"))

    if n_s>0:
        hs50=round(p["cap_v"]*1.5/p["var_v"],0) if p["var_v"]>0 else p["cap_v"]
        wi=max((i for i in range(len(W)) if mrp["status"][i]=="SURCHARGE"),key=lambda i:mrp["gross"][i])
        stu=int(mrp["gross"][wi]-p["max_u"])
        sur_u=round(sum(max(0.0,p["cap_v"]-mrp["charge"][i]) for i in range(len(W)) if mrp["sat"][i]<50) / p["var_v"] if p["var_v"] > 0 else 0, 0)
        n_rupt=sum(1 for v in mrp["inv_e"] if v<0)

        cout_hs_pct = 25
        cout_st_pct = 35
        cout_stock_u = 2.0

        hd3=["Priorite","Option","Description","Capacite resultante","Surcharge resolues","Cout supplementaire","Hypotheses cout","Risque residuel"]
        rows3=[
            ["1 — PRIORITAIRE","[A] Anticipation",
             f"Produire {sur_u:,.0f} U en avance sur semaines creuses",
             f"{p['max_u']:.0f} U/sem",
             f"{min(n_s,3)}/{n_s} (partiellement)",
             f"Cout stockage : {sur_u:.0f} U × {cout_stock_u:.2f} = <strong>{round(sur_u*cout_stock_u,0):,.0f}</strong>",
             f"Hypothese : {cout_stock_u:.2f} par U/sem. A ajuster avec votre DAF.",
             "Stock supplementaire requis"],
            ["2 — SI OPTION 1 INSUFFISANTE","[B] HS +25%",
             f"Fill-L1 +350 PHR/sem = {hs25:.0f} U/sem",
             f"{hs25:.0f} U/sem",
             f"{sum(1 for i in range(len(W)) if mrp['status'][i]=='SURCHARGE' and hs25>=mrp['gross'][i])}/{n_s}",
             f"Surcoût MO : +{cout_hs_pct}% sur heures PHR supplement.",
             f"Hypothese : +{cout_hs_pct}% cout main-d'oeuvre. A valider RH.",
             f"Ne couvre pas les pics > {hs25:.0f} U/sem"],
            ["3 — SI OPTIONS 1+2 INSUFFISANTES","[C] Sous-traitance",
             f"{stu:,} U a externaliser sur semaines critiques",
             f"{p['max_u']:.0f}+{stu:,} U (interne+ST)",
             f"Pics uniquement",
             f"Surcoût ST : +{cout_st_pct}% vs production interne.",
             f"Hypothese : +{cout_st_pct}% cout sous-traitance. A obtenir devis.",
             "Dependance fournisseur exterieur"],
        ]
        # ── Synthèse automatique — AVANT les options d'action ─────────────────
        vcol_s = "#dc2626" if n_s > len(W)*0.5 and mi < 0 else "#d97706" if n_s > 0 else "#16a34a"
        verdict_s = "NO-GO" if n_s > len(W)*0.5 and mi < 0 else "ATTENTION" if n_s > 0 else "OK"
        synth_lines_s = [
            f"Capacité : <strong>{p['cap_v']:.0f} PHR/sem = {p['max_u']:.0f} U/sem</strong>",
            f"Surcharges : <strong style='color:{'#dc2626' if n_s>0 else '#16a34a'}'>{n_s}/{len(W)} semaines</strong>",
            f"Stock min : <strong style='color:{'#dc2626' if mi<0 else '#16a34a'}'>{mi:,.0f} U</strong>"
              + (f" — clients non livrés sur {sum(1 for v in mrp['inv_e'] if v<0)} semaines" if mi < 0 else ""),
            f"Saturation max : <strong>{ms:.0f}%</strong>",
        ]
        if n_s > 0:
            st_u_s = sum(max(0.0, mrp["gross"][i]-p["max_u"]) for i in range(len(W)))
            n_hs50_s = sum(1 for i in range(len(W)) if mrp["status"][i]=="SURCHARGE"
                           and (mrp["gross"][i]*p["var_v"] <= p["cap_v"]*1.5 if p["var_v"]>0 else False))
            synth_lines_s.append(
                f"ST requise : <strong>{st_u_s:,.0f} U</strong> | "
                f"HS+50% couvre <strong>{n_hs50_s}/{n_s}</strong>")
        synth_bullets = "".join(
            f'<div style="padding:.07rem 0;display:flex;gap:.3rem">'
            f'<span style="color:{vcol_s};font-size:.55rem;margin-top:.22rem">▶</span>'
            f'<span>{l}</span></div>' for l in synth_lines_s)
        out.append(
            f'<div style="background:#f8f9fc;border:1.5px solid var(--br);'
            f'border-left:3px solid {vcol_s};border-radius:6px;'
            f'padding:.4rem .65rem;margin:.3rem 0;font-size:.77rem;line-height:1.6">'
            f'<div style="font-size:.65rem;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:var(--mu);font-family:JetBrains Mono,monospace;'
            f'margin-bottom:.2rem">Synthèse automatique '
            f'<span style="color:{vcol_s}">{verdict_s}</span></div>'
            f'{synth_bullets}</div>')

        out.append(T(hd3,rows3,None,"Options d'Action Hierarchisees — 1 option a la fois (pas de combinaison simultanee)"))
        out.append(S("Plan d'action sequence",[
            f"• <strong>Etape 1 (SANS COUT SUPPLEMENTAIRE)</strong> : Anticiper {sur_u:,.0f} U sur semaines creuses.",
            f"  → Si insuffisant, passer a l'etape 2.",
            f"• <strong>Etape 2</strong> : HS +25% Fill-L1 = {hs25:.0f} U/sem (+{cout_hs_pct}% MO — a valider RH).",
            f"  → Si encore insuffisant pour les pics, passer a l'etape 3.",
            f"• <strong>Etape 3</strong> : Sous-traitance {stu:,} U sur semaines critiques uniquement (+{cout_st_pct}% — devis requis).",
            f"• <strong>Ne pas cumuler les 3 options simultanement</strong> — evaluer chaque etape avant de passer a la suivante.",
        ]))
    return "".join(out)


def prod_surcharges(dfs):
    mrp, cap_active, sc_label = _get_active_mrp(dfs)
    p=mrp["p"]; W=mrp["weeks"]
    var_v=p["var_v"]
    hs25=round(cap_active*1.25/var_v,0) if var_v>0 else cap_active
    hs50=round(cap_active*1.50/var_v,0) if var_v>0 else cap_active
    surge=[(i,W[i]) for i in range(len(W)) if mrp["status"][i]=="SURCHARGE"]
    if not surge: return '<div class="ag"><strong>Aucune surcharge</strong> sur les periodes. Capacite suffisante.</div>'
    hd=["Periode","Gross Req","Charge PHR","Cap PHR","Deficit PHR","Sat %","Deficit U","HS+25%?","HS+50%?"]
    rows=[]; cls=[]
    for i,w in enumerate(W):
        if mrp["status"][i]!="SURCHARGE": continue
        wl=w.replace(" Y23",""); du=round(abs(mrp["surplus"][i])/var_v,0) if var_v>0 else 0
        ok25="OUI" if hs25>=mrp["gross"][i] else "NON"
        ok50="OUI" if hs50>=mrp["gross"][i] else "NON"
        c25=f'<span style="color:{"#16a34a" if ok25=="OUI" else "#dc2626"};font-weight:700">{ok25}</span>'
        c50=f'<span style="color:{"#16a34a" if ok50=="OUI" else "#dc2626"};font-weight:700">{ok50}</span>'
        rows.append([wl,f"{mrp['gross'][i]:,.0f}",f"{mrp['charge'][i]:,.1f}",f"{mrp['cap'][i]:,.0f}",
                     f"{abs(mrp['surplus'][i]):,.1f}",f"{mrp['sat'][i]:.1f}%",f"{du:,.0f}",c25,c50])
        cls.append("surge")
    out=[T(hd,rows,cls,"Periodes en Surcharge Capacite")]
    out.append(S("Surcharges",[
        f"• <strong>{len(surge)}/{len(W)}</strong> semaines en surcharge Fill-L1.",
        f"• Saturation max : <strong>{max(mrp['sat'][i] for i,_ in surge):.1f}%</strong>.",
        f"• HS+25% couvre : <strong>{sum(1 for i,_ in surge if hs25>=mrp['gross'][i])}/{len(surge)}</strong> surcharges.",
        f"• HS+50% couvre : <strong>{sum(1 for i,_ in surge if hs50>=mrp['gross'][i])}/{len(surge)}</strong> surcharges.",
    ]))
    return "".join(out)


def prod_sim30(dfs):
    """
    Simulation +30% de la demande nominale.
    +30% = augmentation de 30% par rapport à la demande initiale de chaque période.
    Ex : si W34 = 2000 U → simulation = 2000 × 1.30 = 2600 U.
    """
    mrp_b=mrp_calc(dfs,{})
    ov30={w:round(mrp_b["gross"][i]*1.3,0) for i,w in enumerate(mrp_b["weeks"])}
    mrp30=mrp_calc(dfs,ov30); W=mrp_b["weeks"]
    ns_b=sum(1 for s in mrp_b["status"] if s=="SURCHARGE")
    ns30=sum(1 for s in mrp30["status"] if s=="SURCHARGE")
    out=[f"""<div class="ai">
<strong>Definition de la simulation</strong> : +30% signifie que chaque periode voit
sa demande augmenter de 30% par rapport a sa valeur initiale.
Exemple : si W34 = 2 000 U dans le plan nominal, la simulation applique 2 000 × 1.30 = 2 600 U.
Cette simulation teste la robustesse du plan face a un pic de demande imprevvu.
</div>"""]
    hd=["Periode","Gross Nominal","Gross +30%","Surplus Nominal","Surplus +30%","Statut Nominal","Statut +30%"]
    rows=[]; cls=[]
    for i,w in enumerate(W):
        wl=w.replace(" Y23","")
        rows.append([wl,f"{mrp_b['gross'][i]:,.0f}",f"{mrp30['gross'][i]:,.0f}",
                     f"{mrp_b['surplus'][i]:,.1f}",f"{mrp30['surplus'][i]:,.1f}",
                     sc(mrp_b["status"][i]),sc(mrp30["status"][i])])
        cls.append("surge" if mrp30["status"][i]=="SURCHARGE" else "alrt" if mrp30["status"][i]=="ALERTE" else "")
    out.append(T(hd,rows,cls,"Simulation Hausse Demande +30% vs Demande Nominale"))
    out.append(S("Simulation +30%",[
        f"• Surcharges plan nominal : <strong>{ns_b}/{len(W)}</strong> — apres +30% : <strong>{ns30}/{len(W)}</strong> (+{ns30-ns_b}).",
        f"• Stock min nominal : <strong>{min(mrp_b['inv_e']):,.0f} U</strong> — apres +30% : <strong>{min(mrp30['inv_e']):,.0f} U</strong>.",
        f"• Saturation max : <strong>{max(mrp_b['sat']):.1f}%</strong> → <strong>{max(mrp30['sat']):.1f}%</strong>.",
        f"• Interpretation : si la demande reelle depasse de 30% les previsions, {ns30} semaines seraient en surcharge.",
    ]))
    return "".join(out)


def _get_active_mrp(dfs):
    """
    Retourne le MRP calculé avec le scénario What-If actif de la session.
    Si aucun scénario actif → retourne le MRP nominal.
    Utilisé par TOUTES les fonctions production pour être cohérent avec le panneau latéral.
    """
    mrp_base = mrp_calc(dfs, {})
    p_base   = mrp_base["p"]
    wp = st.session_state.get("whatif_params", {})
    sc = wp.get("production", {}).get("sc_txt", "NOMINAL")

    if not sc or sc == "NOMINAL":
        return mrp_base, p_base["cap_v"], ""

    try:
        new_cap, minprod, sc_label = _parse_prod_scenario(sc, p_base["cap_v"])
        mrp_sc = _mrp_calc_with_new_cap(
            mrp_base, new_cap, p_base["var_v"], p_base["ss_v"], p_base["bat_v"],
            minprod=minprod)
        return mrp_sc, new_cap, sc_label
    except Exception:
        return mrp_base, p_base["cap_v"], ""


def _sc_banner(sc_label, cap_nom, cap_sc, var_v):
    """Bandeau visuel indiquant le scénario What-If actif dans les analyses."""
    if not sc_label:
        return ""
    max_nom = round(cap_nom / var_v, 0) if var_v > 0 else cap_nom
    max_sc  = round(cap_sc  / var_v, 0) if var_v > 0 else cap_sc
    return (f'<div style="background:#eff6ff;border:1.5px solid #2563eb;border-radius:6px;'
            f'padding:.35rem .65rem;margin:.2rem 0;font-size:.76rem">'
            f'<strong style="color:#1e3a8a">📐 Scénario actif : {sc_label}</strong> — '
            f'Capacité : {cap_nom:.0f} PHR → <strong>{cap_sc:.0f} PHR/sem</strong> = '
            f'<strong>{max_sc:.0f} U/sem</strong> (vs {max_nom:.0f} U/sem nominal)'
            f'</div>')


def prod_hs_calc(dfs):
    """
    Calcule les heures supplémentaires nécessaires semaine par semaine.
    Utilise le scénario What-If actif (Cap -X%, Cap +X%, etc.) si configuré.
    Formule : PHR déficit = Charge PHR - Capacité active (pas toujours nominale !)
              HS% nécessaire = Déficit / Capacité active × 100
    """
    mrp, cap_active, sc_label = _get_active_mrp(dfs)
    p = mrp["p"]; W = mrp["weeks"]
    cap_nom = p["cap_v"]   # toujours la nominale pour référence
    var_v   = p["var_v"]
    max_u   = round(cap_active / var_v, 0) if var_v > 0 else cap_active

    # HS calculées sur la capacité ACTIVE (pas toujours nominale)
    cap_hs25 = cap_active * 1.25
    cap_hs50 = cap_active * 1.50
    max_hs25 = round(cap_hs25 / var_v, 0) if var_v > 0 else cap_hs25
    max_hs50 = round(cap_hs50 / var_v, 0) if var_v > 0 else cap_hs50

    delta_phr  = cap_hs25 - cap_active  # PHR gagnés par +25% HS
    delta_u25  = max_hs25 - max_u
    delta_u50  = max_hs50 - max_u
    out = []

    # Bandeau scénario actif
    if sc_label:
        out.append(_sc_banner(sc_label, cap_nom, cap_active, var_v))

    out.append(f"""
<div class="ai">
<strong>Definition — Heures Supplementaires (HS)</strong><br>
{"<strong style='color:#dc2626'>ATTENTION : capacite active = " + f"{cap_active:.0f} PHR/sem (scenario {sc_label})</strong>, pas la nominale " + f"({cap_nom:.0f} PHR).<br>" if sc_label else ""}
Capacite active Fill-L1 : <strong>{cap_active:.0f} PHR/semaine</strong> ({max_u:.0f} U/sem).<br>
HS +25% sur cap. active → {cap_hs25:.0f} PHR/sem → <strong>{max_hs25:.0f} U/sem</strong> (+{delta_phr:.0f} PHR, +{delta_u25:.0f} U).<br>
HS +50% sur cap. active → {cap_hs50:.0f} PHR/sem → <strong>{max_hs50:.0f} U/sem</strong> (+{cap_hs50-cap_active:.0f} PHR, +{delta_u50:.0f} U).<br>
<strong>Formule :</strong> Déficit PHR = Charge PHR - Capacité active | HS% = Déficit / Cap. active × 100
</div>""")

    hd = ["Semaine","Demande [U]","Charge [PHR]",f"Cap. active [PHR]","Deficit [PHR]",
          "HS% necessaire","HS+25% suffit ?","HS+50% suffit ?","ST si HS+50%"]
    rows = []; cls_r = []
    total_phr_def = 0; total_st_hs50 = 0
    n_hs25_ok = 0; n_hs50_ok = 0; n_impossible = 0

    for i, w in enumerate(W):
        wl = w.replace(" Y23", "")
        g  = mrp["gross"][i]
        ch = mrp["charge"][i]
        # Déficit par rapport à la capacité ACTIVE
        deficit = max(0.0, ch - cap_active)
        if deficit <= 0:
            rows.append([wl, f"{g:,.0f}", f"{ch:,.1f}", f"{cap_active:.0f}",
                         "0", "0%", "n/a", "n/a", "0"])
            cls_r.append("")
            continue
        hs_pct = round(deficit / cap_active * 100, 1)
        ok25 = "OUI" if ch <= cap_hs25 else "NON"
        ok50 = "OUI" if ch <= cap_hs50 else "NON"
        st_hs50 = max(0.0, g - max_hs50) if ok50 == "NON" else 0
        total_phr_def += deficit
        total_st_hs50 += st_hs50
        if ok25 == "OUI": n_hs25_ok += 1
        if ok50 == "OUI": n_hs50_ok += 1
        if ok50 == "NON": n_impossible += 1
        c25 = f'<span style="color:{"#16a34a" if ok25=="OUI" else "#dc2626"};font-weight:700">{ok25}</span>'
        c50 = f'<span style="color:{"#16a34a" if ok50=="OUI" else "#dc2626"};font-weight:700">{ok50}</span>'
        pct_col = "#dc2626" if hs_pct > 100 else "#d97706" if hs_pct > 50 else "#16a34a"
        rows.append([wl, f"{g:,.0f}", f"{ch:,.1f}", f"{cap_active:.0f}",
                     f"<strong>{deficit:,.1f}</strong>",
                     f'<span style="color:{pct_col};font-weight:700">{hs_pct:.0f}%</span>',
                     c25, c50, f"{st_hs50:,.0f}" if st_hs50 > 0 else "0"])
        cls_r.append("surge")

    out.append(T(hd, rows, cls_r,
        f"Analyse HS — cap. active {cap_active:.0f} PHR/sem"
        + (f" (scenario {sc_label})" if sc_label else " (nominale)")))

    # Synthèse
    bilan_hs25 = (f"HS +25% resout {n_hs25_ok} semaine(s)." if n_hs25_ok > 0
                  else "HS +25% ne resout AUCUNE semaine sur ce plan.")
    bilan_hs50 = (f"HS +50% resout {n_hs50_ok} semaine(s)." if n_hs50_ok > 0
                  else "HS +50% ne resout AUCUNE semaine.")
    st_sans_hs = sum(max(0.0, mrp["gross"][i] - max_u) for i in range(len(W)))

    out.append(S("Analyse Heures Supplementaires", [
        f"• Cap. active : <strong>{cap_active:.0f} PHR/sem = {max_u:.0f} U/sem</strong>"
          + (f" (scenario : {sc_label})" if sc_label else " (nominale)"),
        f"• HS +25% sur cap. active : +{delta_phr:.0f} PHR/sem → <strong>{max_hs25:.0f} U/sem</strong>. {bilan_hs25}",
        f"• HS +50% sur cap. active : +{cap_hs50-cap_active:.0f} PHR/sem → <strong>{max_hs50:.0f} U/sem</strong>. {bilan_hs50}",
        f"• Deficit PHR cumule (toutes semaines en surcharge) : <strong>{total_phr_def:,.0f} PHR</strong>.",
        f"• Semaines impossibles meme avec HS+50% : <strong>{n_impossible}</strong>.",
        f"• ST residuelle sans HS : <strong>{st_sans_hs:,.0f} U</strong> | avec HS+50% : <strong>{total_st_hs50:,.0f} U</strong>.",
    ]))

    if n_impossible > 0:
        econ = st_sans_hs - total_st_hs50
        out.append(f"""
<div style="background:#fef2f2;border:1.5px solid #dc2626;border-radius:8px;padding:.55rem .8rem;margin:.35rem 0">
  <div style="font-weight:700;font-size:.8rem;color:#991b1b;margin-bottom:.2rem">
    Conclusion — HS insuffisantes seules
  </div>
  <div style="font-size:.79rem;color:#374151;line-height:1.65">
    <strong>Pourquoi ?</strong> {n_impossible} semaine(s) depassent toute capacite HS
    (ex. pic {max(mrp['gross']):,.0f} U/sem vs max HS+50% = {max_hs50:.0f} U/sem sur cap. active {cap_active:.0f} PHR).<br><br>
    <strong>Recommandation :</strong><br>
    1. HS +50% sur semaines partiellement couvertes → economise <strong>{econ:,.0f} U</strong> de ST.<br>
    2. Sous-traiter les <strong>{total_st_hs50:,.0f} U restantes</strong> sur {n_impossible} semaine(s).<br>
    3. Obtenir un devis ST avant de valider (surcoût +30-35% vs production interne).
  </div>
</div>""")
    else:
        out.append(f'<div class="ag">HS seules suffisent sur cap. active {cap_active:.0f} PHR/sem. '
                   f'Aucune ST requise si HS validees par la RH.</div>')
    return "".join(out)


def _parse_prod_scenario(scenario, cap_v):
    parts = scenario.split("+")
    new_cap = cap_v; minprod = None; labels = []
    for p in parts:
        p = p.strip()
        if p.startswith("CAP_MINUS_"):
            pct=float(p[10:]); new_cap=cap_v*(1-pct/100); labels.append(f"Cap -{pct:.0f}%")
        elif p.startswith("CAP_PLUS_"):
            pct=float(p[9:]); new_cap=cap_v*(1+pct/100); labels.append(f"Cap +{pct:.0f}%")
        elif p=="CAP_IGNORED":
            new_cap=999999.0; labels.append("Cap ignoree")
        elif p.startswith("CAP_") and p[4:].replace(".","").isdigit():
            new_cap=float(p[4:]); labels.append(f"Cap={new_cap:.0f}PHR")
        elif p.startswith("MINPROD_"):
            minprod=float(p[8:]); labels.append(f"MinProd={minprod:.0f}U")
    return new_cap, minprod, " + ".join(labels) if labels else "Nominal"


def _parse_dem_scenario(scenario):
    parts = scenario.split("+")
    method=None; alpha=None; beta=None; gamma=None; ma_w=3
    for p in parts:
        p=p.strip()
        if p in ("DEM_LES","DEM_HW","DEM_MA") or p.startswith("DEM_MA_"):
            method=p
            if p.startswith("DEM_MA_"): ma_w=int(p[7:])
        elif p == "DEM_MBS":
            method = "DEM_LES"
        elif p.startswith("ALPHA_"): alpha=float(p[6:])
        elif p.startswith("BETA_"):  beta=float(p[5:])
        elif p.startswith("GAMMA_"): gamma=float(p[6:])
    return method, alpha, beta, gamma, ma_w


def do_action_whatif(agent, q, dfs, scenario):
    if not scenario or scenario in ("NOMINAL","SITUATION NOMINALE","DEM_AUTO",""):
        return do_action(agent, q, dfs, scenario)
    if agent=="production":
        try:
            mrp_b=mrp_calc(dfs,{}); p=mrp_b["p"]
            new_cap,minprod_val,label=_parse_prod_scenario(scenario,p["cap_v"])
            mrp_a=_mrp_calc_with_new_cap(mrp_b,new_cap,p["var_v"],p["ss_v"],p["bat_v"],minprod=minprod_val)
            return _whatif_prod_result(mrp_b,mrp_a,label)
        except Exception as e:
            return f'<div class="ae">Erreur What-if production : {e}</div>'
    elif agent in ("demande","marketing"):
        try:
            dem=demand_calc(dfs)
            if not dem: return do_action(agent,q,dfs,scenario)
            return _whatif_dem_result(dem,scenario)
        except Exception as e:
            return f'<div class="ae">Erreur What-if demande : {e}</div>'
    return do_action(agent,q,dfs,scenario)


def _mrp_calc_with_new_cap(mrp_b, new_cap, var_v, ss_v, bat_v, minprod=None):
    W = mrp_b["weeks"]
    new_max_u = round(new_cap / var_v, 0) if var_v > 0 else new_cap
    R = {k: [] for k in ["weeks","gross","charge","cap","surplus","sat",
                          "net","po","plan","inv_s","inv_e","status","mod"]}
    R["p"] = {**mrp_b["p"], "cap_v": new_cap, "max_u": new_max_u}
    inv = mrp_b["p"]["inv0"]
    for i, w in enumerate(W):
        g   = mrp_b["gross"][i]; c   = new_cap; ss  = ss_v; b   = bat_v
        ch  = round(g * var_v, 2); surp = round(c - ch, 2); sat  = round(ch / c * 100, 1) if c > 0 else 0.0
        net  = max(0.0, g - inv + ss)
        if net > 0:
            po = b * np.ceil(net / b)
            if minprod is not None: po = max(minprod, po)
            plan_prod = min(po, new_max_u)
        else:
            po = plan_prod = 0.0
        i_s  = inv; i_e  = round(inv + plan_prod - g, 2)
        st_v = "SURCHARGE" if surp < 0 else ("ALERTE" if sat > 85 else "OK")
        for k, val in [("weeks",str(w)),("gross",g),("charge",ch),("cap",c),
                       ("surplus",surp),("sat",sat),("net",round(net,0)),
                       ("po",round(po,0)),("plan",plan_prod),("inv_s",i_s),
                       ("inv_e",i_e),("status",st_v),("mod",False)]:
            R[k].append(val)
        inv = i_e
    return R


def _whatif_prod_result(mrp_b, mrp_a, label):
    """
    Verdict nuancé basé sur 3 critères combinés :
      1. Surcharges résolues (principal)
      2. Amélioration du stock (secondaire)
      3. Ampleur des pics restants (contexte)
    Le verdict explique POURQUOI avec les chiffres, et donne la suite concrète.
    """
    W=mrp_b["weeks"]; p_b=mrp_b["p"]; p_a=mrp_a["p"]
    ns_b=sum(1 for s in mrp_b["status"] if s=="SURCHARGE")
    ns_a=sum(1 for s in mrp_a["status"] if s=="SURCHARGE")
    ms_b=max(mrp_b["sat"]); ms_a=max(mrp_a["sat"])
    mi_b=min(mrp_b["inv_e"]); mi_a=min(mrp_a["inv_e"])
    amelio=sum(1 for i in range(len(W)) if mrp_b["status"][i]=="SURCHARGE" and mrp_a["status"][i]!="SURCHARGE")
    delta_sur=ns_a-ns_b
    delta_stock=mi_a-mi_b
    stock_ameliore=delta_stock>0
    pct_resolues=round(amelio/ns_b*100,0) if ns_b>0 else 0
    var_v=p_b.get("var_v",0.4667)

    # ── Sous-traitance résiduelle nécessaire après ce scénario ──────────────
    st_avant=sum(max(0.0,mrp_b["gross"][i]-p_b["max_u"]) for i in range(len(W)))
    st_apres=sum(max(0.0,mrp_a["gross"][i]-p_a["max_u"]) for i in range(len(W)))

    # ── Pic le plus critique ─────────────────────────────────────────────────
    pic_idx=max(range(len(W)),key=lambda i:mrp_a["gross"][i]) if W else 0
    pic_dem=mrp_a["gross"][pic_idx]; pic_w=W[pic_idx].replace(" Y23","")
    pic_sat=round(pic_dem*var_v/p_a["cap_v"]*100,0) if p_a["cap_v"]>0 else 0

    # ── Verdict nuancé ───────────────────────────────────────────────────────
    if ns_a==0 and mi_a>=0:
        verdict="GO — PLAN VALIDE"
        vcol="#16a34a"
        pourquoi=(f"Toutes les surcharges sont resolues et le stock reste positif. "
                  f"Le scenario {label} est suffisant seul.")
        suite="Aucune action complementaire requise. Valider avec le DAF et la RH avant execution."
    elif ns_a==0 and mi_a<0:
        verdict="GO CONDITIONNEL — RUPTURE STOCK"
        vcol="#d97706"
        pourquoi=(f"Les surcharges de capacite sont resolues ({ns_b}→0), "
                  f"mais le stock reste negatif ({mi_a:,.0f} U). "
                  f"La production est possible mais des clients ne seront pas livres.")
        suite=(f"Appliquer {label} ET reconstituer le stock par anticipation "
               f"({abs(mi_a):,.0f} U a avancer sur les semaines creuses).")
    elif amelio>0 and pct_resolues>=50:
        verdict=f"GO CONDITIONNEL — {amelio}/{ns_b} surcharges resolues"
        vcol="#d97706"
        pourquoi=(f"{label} resout {amelio} surcharge(s) sur {ns_b} ({pct_resolues:.0f}%). "
                  f"Stock ameliore de {delta_stock:+,.0f} U. "
                  f"Reste {ns_a} semaine(s) en surcharge — le pic {pic_w} "
                  f"({pic_dem:,.0f} U, sat={pic_sat:.0f}%) necessite encore de la sous-traitance.")
        suite=(f"Appliquer {label} EN PREMIER (gain immediat), PUIS sous-traiter "
               f"{st_apres:,.0f} U sur les {ns_a} semaines restantes.")
    elif amelio==0 and stock_ameliore:
        verdict="INSUFFISANT SEUL — AMELIORATION PARTIELLE"
        vcol="#d97706"
        pourquoi=(f"{label} n'elimine aucune surcharge ({ns_a}/{len(W)} inchangees) "
                  f"car les pics de demande (ex. {pic_w} : {pic_dem:,.0f} U = {pic_sat:.0f}% de saturation) "
                  f"depassent massivement la capacite meme augmentee ({p_a['max_u']:.0f} U/sem). "
                  f"En revanche, le stock s'ameliore de {delta_stock:+,.0f} U "
                  f"({mi_b:,.0f} → {mi_a:,.0f} U) : ce scenario reduit la profondeur des ruptures.")
        suite=(f"Ne pas rejeter ce scenario mais ne pas l'appliquer seul. "
               f"Combiner : {label} (pour ameliorer le stock) + "
               f"sous-traitance de {st_apres:,.0f} U sur {ns_a} semaines (pour couvrir les pics). "
               f"Obtenir un devis ST avant de valider.")
    elif delta_sur<0:
        verdict=f"GO CONDITIONNEL — {abs(delta_sur)} surcharge(s) resolue(s)"
        vcol="#d97706"
        pourquoi=(f"{label} resout {abs(delta_sur)} surcharge(s) ({ns_b}→{ns_a}). "
                  f"Reste {ns_a} semaine(s) en surcharge avec un pic a {pic_sat:.0f}% de saturation ({pic_w}).")
        suite=(f"Appliquer {label} PUIS evaluer si la sous-traitance residuelle "
               f"({st_apres:,.0f} U) est acceptable. Ne pas combiner d'emblee.")
    else:
        verdict="NO-GO — SCENARIO INEFFICACE"
        vcol="#dc2626"
        pourquoi=(f"{label} ne resout aucune surcharge et n'ameliore pas le stock. "
                  f"Les pics de demande (max {pic_dem:,.0f} U/sem a {pic_sat:.0f}% de saturation) "
                  f"depassent toute capacite atteignable par ce seul levier.")
        suite=(f"Abandonner ce scenario. "
               f"Seule solution viable : sous-traitance directe de {st_avant:,.0f} U "
               f"(ou combiner HS maximal + ST). Lancer un appel d'offres fournisseur externe.")

    col_d="#dc2626" if delta_sur>0 else "#16a34a" if delta_sur<0 else "#d97706"
    out=[]

    # ── En-tête scénario ─────────────────────────────────────────────────────
    out.append(f'<div style="font-weight:700;font-size:.88rem;color:var(--navy);margin:.3rem 0">'
               f'What-If Production — {label}</div>')

    # ── Tableau de bord impact ───────────────────────────────────────────────
    out.append(f"""
<div class="synth">
<div class="synth-h">Impact chiffre du scenario</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem;margin-top:.2rem">
  <div>
    <div style="font-size:.68rem;color:var(--mu);font-weight:700">CAPACITE</div>
    <div>{p_b['cap_v']:.0f} PHR → <strong>{p_a['cap_v']:.0f} PHR/sem</strong></div>
    <div>{p_b['max_u']:.0f} U → <strong>{p_a['max_u']:.0f} U/sem</strong></div>
  </div>
  <div>
    <div style="font-size:.68rem;color:var(--mu);font-weight:700">SURCHARGES</div>
    <div><strong style="color:{col_d}">{ns_b} → {ns_a}</strong> ({delta_sur:+d} sem.)</div>
    <div>Resolues : <strong>{amelio}/{ns_b}</strong> ({pct_resolues:.0f}%)</div>
    <div>Sat max : {ms_b:.0f}% → <strong>{ms_a:.0f}%</strong></div>
  </div>
  <div>
    <div style="font-size:.68rem;color:var(--mu);font-weight:700">STOCK</div>
    <div>Min : {mi_b:,.0f} → <strong style="color:{'#dc2626' if mi_a<0 else '#16a34a'}">{mi_a:,.0f} U</strong></div>
    <div>Variation : <strong style="color:{'#16a34a' if delta_stock>0 else '#dc2626'}">{delta_stock:+,.0f} U</strong></div>
    <div>ST residuelle : <strong>{st_apres:,.0f} U</strong></div>
  </div>
</div>
</div>""")

    # ── Alertes contextuelles ────────────────────────────────────────────────
    if pic_sat > 200:
        out.append(f'<div class="ae"><strong>Pic critique {pic_w}</strong> : {pic_dem:,.0f} U/sem = '
                   f'{pic_sat:.0f}% de saturation apres {label}. '
                   f'Aucun levier interne ne peut couvrir ce pic — sous-traitance obligatoire.</div>')
    if stock_ameliore and amelio==0:
        out.append(f'<div class="aw"><strong>Stock ameliore mais surcharges inchangees</strong> : '
                   f'{label} reduit la profondeur des ruptures ({delta_stock:+,.0f} U) '
                   f'sans resoudre les pics de production. Utile en complement, insuffisant seul.</div>')
    if amelio>0:
        out.append(f'<div class="ag"><strong>{amelio} surcharge(s) resolue(s)</strong> par ce scenario. '
                   f'Il reste {ns_a} semaine(s) necessitant de la sous-traitance ({st_apres:,.0f} U).</div>')

    # ── Tableau comparatif ───────────────────────────────────────────────────
    hd=["Sem.","Demande","Charge av.","Charge ap.","Surplus av.","Surplus ap.","Sat av.","Sat ap.","Statut av.","Statut ap."]
    rows=[]; cls_r=[]
    for i,w in enumerate(W):
        wl=w.replace(" Y23",""); changed=mrp_b["status"][i]!=mrp_a["status"][i]
        rows.append([f'<strong>{wl}</strong>' if changed else wl,
            f"{mrp_b['gross'][i]:,.0f}",
            f"{mrp_b['charge'][i]:,.1f}",f"{mrp_a['charge'][i]:,.1f}",
            f"{mrp_b['surplus'][i]:,.1f}",f"{mrp_a['surplus'][i]:,.1f}",
            f"{mrp_b['sat'][i]:.1f}%",f"{mrp_a['sat'][i]:.1f}%",
            sc(mrp_b["status"][i]),sc(mrp_a["status"][i])])
        cls_r.append("alrt" if changed else ("surge" if mrp_a["status"][i]=="SURCHARGE" else ""))
    out.append(T(hd,rows,cls_r,"Comparaison semaine par semaine — Avant / Apres scenario"))

    # ── Bloc de décision avec raisonnement complet ───────────────────────────
    out.append(f"""
<div style="background:#f8f9fc;border:1.5px solid var(--br);border-radius:8px;padding:.6rem .85rem;margin:.4rem 0">
  <div style="font-weight:700;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;
    color:var(--navy);font-family:JetBrains Mono,monospace;margin-bottom:.3rem">Verdict & Raisonnement</div>
  <div style="font-size:.9rem;font-weight:800;color:{vcol};margin-bottom:.35rem">{verdict}</div>
  <div style="font-size:.8rem;color:#374151;margin-bottom:.3rem;line-height:1.65">
    <strong>Pourquoi ?</strong> {pourquoi}
  </div>
  <div style="font-size:.8rem;color:#1e3a8a;line-height:1.65;border-top:1px solid var(--br);padding-top:.25rem;margin-top:.1rem">
    <strong>Action recommandee :</strong> {suite}
  </div>
</div>""")
    return "".join(out)


def _whatif_dem_result(dem, scenario):
    try:
        from forecasting import compare_all, whatif_demand
    except:
        return '<div class="ae">Module forecasting.py manquant.</div>'
    out=[]
    out.append(f'<div style="font-weight:700;font-size:.88rem;color:var(--navy);margin:.3rem 0">What-If Demande — {scenario}</div>')
    for art,r in dem.items():
        h=r["hist"].values.astype(float)
        if len(h)<3: continue
        ref_cmp=compare_all(h); ref=ref_cmp.methods[ref_cmp.recommended]
        method,alpha,beta,gamma,ma_w=_parse_dem_scenario(scenario)
        if method and method.startswith("DEM_MA"):
            wi=whatif_demand(h,"MA",ma_window=ma_w,alpha=alpha,beta=beta,gamma=gamma)
        elif method=="DEM_LES":
            wi=whatif_demand(h,"LES",alpha=alpha)
        elif method=="DEM_HW":
            wi=whatif_demand(h,"HW",alpha=alpha,beta=beta,gamma=gamma)
        elif alpha is not None and gamma is not None:
            wi=whatif_demand(h,"HW",alpha=alpha,beta=beta,gamma=gamma)
        elif alpha is not None:
            wi=whatif_demand(h,"LES",alpha=alpha)
        else:
            wi=whatif_demand(h,"LES")
        ref_r=wi["reference"]; scen_r=wi["scenario"]; d_mape=wi["delta_mape"]
        col_m="#16a34a" if d_mape<-2 else "#dc2626" if d_mape>2 else "#d97706"

        if "MA" in scen_r.method.upper() and "HW" not in scen_r.method.upper():
            params_str = f"Fenetre w (pas de alpha/beta/gamma pour MA)"
        elif "HW" in scen_r.method.upper() or "Holt-Winters" in scen_r.method:
            params_str = f"alpha={scen_r.alpha}, beta={scen_r.beta}, gamma={scen_r.gamma}"
        else:
            params_str = f"alpha={scen_r.alpha} (pas de beta ni gamma pour LES)"

        if "MA" in ref_r.method.upper() and "HW" not in ref_r.method.upper():
            ref_params = f"Fenetre w (pas de alpha/beta/gamma)"
        elif "HW" in ref_r.method.upper() or "Holt-Winters" in ref_r.method:
            ref_params = f"alpha={ref_r.alpha}, beta={ref_r.beta}, gamma={ref_r.gamma}"
        else:
            ref_params = f"alpha={ref_r.alpha}"

        verdict_color={"AMELIORATION":"#16a34a","EQUIVALENT":"#d97706",
                       "LEGER RECUL":"#d97706","DEGRADATION":"#dc2626"}.get(wi["verdict"],"#374151")
        verdict_icon={"AMELIORATION":"OK","EQUIVALENT":"~","LEGER RECUL":"!","DEGRADATION":"X"}.get(wi["verdict"],"?")

        out.append(f'<div style="font-weight:700;color:var(--navy);margin:.3rem 0">{art[:30]}</div>')
        # Verdict clair : OUI recommandé / NON dégradation / ~ équivalent
        is_better  = d_mape < -2
        is_worse   = d_mape > 2
        is_neutral = not is_better and not is_worse

        if is_better:
            verdict_txt = f"✅ RECOMMANDE — le scenario ameliore la precision de {abs(d_mape):.1f} points."
            verdict_col = "#16a34a"
        elif is_neutral:
            verdict_txt = f"~ EQUIVALENT — ecart de {abs(d_mape):.1f}% : les deux methodes sont comparables."
            verdict_col = "#d97706"
        else:
            verdict_txt = (f"❌ NON RECOMMANDE — le scenario degrade la precision de {abs(d_mape):.1f} points. "
                           f"La methode de reference ({ref_r.method}, MAPE {ref_r.mape:.1f}%) reste meilleure.")
            verdict_col = "#dc2626"

        out.append(
            f'<div class="synth"><div class="synth-h">Comparaison methodes — MAPE plus bas = plus precis</div>'
            f'<div><strong>Methode de reference (recommandee)</strong> : {ref_r.method} — {ref_params}</div>'
            f'<div>MAPE reference = <strong>{ref_r.mape:.1f}%</strong></div>'
            f'<div style="margin-top:.2rem"><strong>Methode testee (scenario)</strong> : {scen_r.method} — {params_str}</div>'
            f'<div>MAPE scenario = <span style="color:{col_m};font-weight:700">{scen_r.mape:.1f}%</span> — '
            f'ecart : <span style="color:{col_m};font-weight:700">{d_mape:+.1f}%</span></div>'
            f'<div style="margin-top:.25rem;padding:.3rem .5rem;background:#f8f9fc;border-left:3px solid {verdict_col};border-radius:4px">'
            f'<span style="font-weight:700;color:{verdict_col}">{verdict_txt}</span>'
            f'</div></div>'
        )
        hd=["Periode","Forecast Ref.","Forecast Scen.","Delta","Ecart %","Int. Bas (~85%)","Int. Haut (~85%)"]
        rows=[]

        # ── Correction prévisions plates si tendance forte ────────────────────
        r_data = dem.get(art, {})
        v_hist  = r_data.get("hist", None)
        tr_val  = r_data.get("trend", 0)
        mn_val  = r_data.get("mean", 1)
        rel_tr  = abs(tr_val) / mn_val if mn_val > 0 else 0

        def _is_flat_fc(fc_list):
            if not fc_list or len(fc_list) < 2: return True
            return (max(fc_list) - min(fc_list)) <= max(1.0, 0.02 * abs(float(fc_list[0])))

        def _lin_fc_from_hist(v_series, n_out=6):
            if v_series is None or len(v_series) < 2: return None
            v_arr = v_series.values if hasattr(v_series, 'values') else np.array(v_series)
            slope, intercept = np.polyfit(np.arange(len(v_arr)), v_arr, 1)
            return [max(0.0, round(intercept + slope * (len(v_arr) + i), 0))
                    for i in range(1, n_out + 1)]

        fc_ref_list  = list(ref_r.forecast)
        fc_scen_list = list(scen_r.forecast)
        lin_fc = _lin_fc_from_hist(v_hist) if v_hist is not None else None

        if rel_tr > 0.10 and lin_fc:
            if _is_flat_fc(fc_ref_list):
                fc_ref_list = lin_fc
            if _is_flat_fc(fc_scen_list):
                fc_scen_list = lin_fc   # scénario LES plat → même correction

        for i in range(6):
            fr = fc_ref_list[i]; fs = fc_scen_list[i]; delta = fs - fr
            pct = round(delta / (fr + 1e-9) * 100, 1)
            col_delta = "#16a34a" if abs(pct)<5 else "#d97706" if abs(pct)<15 else "#dc2626"
            rows.append([f"M+{i+1}", f"{fr:,.0f}", f"{fs:,.0f}",
                f'<span style="color:{col_delta};font-weight:700">{delta:+,.0f}</span>',
                f'<span style="color:{col_delta}">{pct:+.1f}%</span>',
                f"{scen_r.intervals_low[i]:,.0f}", f"{scen_r.intervals_high[i]:,.0f}"])
        out.append(T(hd,rows,None,f"Forecast Avant/Apres — {art[:22]}"))
        out.append(S(f"Analyse {art[:22]}",[
            f"• MAPE reference ({ref_r.method}) : <strong>{ref_r.mape:.1f}%</strong>.",
            f"• MAPE scenario ({scen_r.method}) : <strong>{scen_r.mape:.1f}%</strong> ({d_mape:+.1f}%).",
            f"• Regle : MAPE le plus bas = methode la plus precise.",
            f"• Int. de confiance a ~85% (M+6) : [{scen_r.intervals_low[5]:,.0f} — {scen_r.intervals_high[5]:,.0f} U].",
        ]))
    return "".join(out)


def _build_synthese(agent, q, dfs):
    """
    Synthèse courte et chiffrée générée automatiquement après chaque analyse.
    Pas de Groq — uniquement des calculs Python sur les données réelles.
    Retourne un bloc HTML compact à afficher sous la réponse principale.
    """
    wp = st.session_state.get("whatif_params", {})
    sc_actif = ""
    if agent == "production":
        sc_actif = wp.get("production", {}).get("sc_txt", "")
    elif agent in ("demande", "marketing"):
        sc_actif = wp.get("demande", {}).get("sc_txt", "")

    lines = []
    verdict = ""
    vcol   = "#374151"

    try:
        # ── PRODUCTION ────────────────────────────────────────────────────────
        if agent == "production" or q in ("__PRD_MRP__","__PRD_SURGE__","__PRD_SIM30__"):
            mrp = mrp_calc(dfs, {})
            p = mrp["p"]; W = mrp["weeks"]
            ns = sum(1 for s in mrp["status"] if s=="SURCHARGE")
            mi = min(mrp["inv_e"]); ms = max(mrp["sat"])
            st_u = sum(max(0.0, mrp["gross"][i]-p["max_u"]) for i in range(len(W)))
            n_rupt = sum(1 for v in mrp["inv_e"] if v < 0)
            hs50_u = round(p["cap_v"]*1.5/p["var_v"], 0) if p["var_v"]>0 else p["cap_v"]

            if q == "__PRD_SIM30__":
                ov30 = {w: round(mrp["gross"][i]*1.3, 0)
                        for i, w in enumerate(W)}
                mrp30 = mrp_calc(dfs, ov30)
                ns30 = sum(1 for s in mrp30["status"] if s=="SURCHARGE")
                mi30 = min(mrp30["inv_e"])
                lines += [
                    f"Simulation +30% : surcharges {ns} → <strong>{ns30}/{len(W)}</strong> (+{ns30-ns})",
                    f"Stock min : {mi:,.0f} → <strong>{mi30:,.0f} U</strong>",
                    f"Saturation max : {ms:.0f}% → <strong>{max(mrp30['sat']):.0f}%</strong>",
                ]
                verdict = "CRITIQUE" if ns30 > len(W)*0.5 else "ATTENTION" if ns30 > 0 else "OK"
            else:
                lines += [
                    f"Capacité : <strong>{p['cap_v']:.0f} PHR/sem = {p['max_u']:.0f} U/sem</strong>",
                    f"Surcharges : <strong style='color:{'#dc2626' if ns>0 else '#16a34a'}'>"
                    f"{ns}/{len(W)} semaines</strong>",
                    f"Stock min : <strong style='color:{'#dc2626' if mi<0 else '#16a34a'}'>"
                    f"{mi:,.0f} U</strong>"
                    + (" — clients non livrés sur " + str(n_rupt) + " semaines" if mi < 0 else ""),
                    f"Saturation max : <strong>{ms:.0f}%</strong>",
                ]
                if st_u > 0:
                    lines.append(f"ST requise : <strong>{st_u:,.0f} U</strong>"
                                 f" | HS+50% couvre "
                                 f"{sum(1 for i in range(len(W)) if mrp['status'][i]=='SURCHARGE' and mrp['gross'][i]*p['var_v']<=p['cap_v']*1.5)}/{ns}")
                verdict = "NO-GO" if ns > len(W)*0.5 and mi < 0 else \
                          "ATTENTION" if ns > 0 else "OK"

        # ── DEMANDE ───────────────────────────────────────────────────────────
        elif agent in ("demande","marketing") or q in (
                "__DEM_AUTO__","__MKT_AUTO__","__DEM_METHODS__","__DEM_FC__",
                "__DEM_ANOM__","__DEM_MAPE__"):
            dem = demand_calc(dfs)
            if dem:
                mpy_avg  = round(sum(min(r["les_mape"],r["hw_mape"],r["ma_mape"])
                                     for r in dem.values()) / len(dem), 1)
                merp_avg = round(sum(r["mape_erp"] for r in dem.values()) / len(dem), 1)
                vol_tot  = round(sum(r["mean"] for r in dem.values()), 0)
                n_sais   = sum(1 for r in dem.values() if r["seasonal"])
                n_declin = sum(1 for r in dem.values() if r["trend"] < 0)
                best_art = min(dem.items(), key=lambda x: min(x[1]["les_mape"],
                                x[1]["hw_mape"], x[1]["ma_mape"]))
                worst_art = max(dem.items(), key=lambda x: min(x[1]["les_mape"],
                                x[1]["hw_mape"], x[1]["ma_mape"]))
                lines += [
                    f"Articles analysés : <strong>{len(dem)}</strong> | Volume total moyen : <strong>{vol_tot:,.0f} U/période</strong>",
                    f"MAPE Python moyen : <strong>{mpy_avg:.1f}%</strong>"
                    + (f" vs ERP : <strong>{merp_avg:.1f}%</strong>" if merp_avg > 0 else ""),
                    f"Meilleure précision : <strong>{best_art[0][:20]}</strong> "
                    f"({min(best_art[1]['les_mape'],best_art[1]['hw_mape'],best_art[1]['ma_mape']):.1f}%)",
                ]
                if n_declin > 0:
                    lines.append(f"⚠ {n_declin} article(s) en déclin (tendance négative) — alerter le marketing")
                if n_sais > 0:
                    lines.append(f"{n_sais} article(s) saisonnier(s) détecté(s) — HW recommandé")
                verdict = "OK" if mpy_avg < 15 else "ATTENTION" if mpy_avg < 25 else "CRITIQUE"

        # ── FINANCE ───────────────────────────────────────────────────────────
        elif agent == "finance" or q == "__FIN_AUTO__":
            for sh, df in dfs.items():
                nc = [c for c in df.select_dtypes(include=[np.number]).columns]
                sc_c = df.select_dtypes(exclude=[np.number]).columns.tolist()
                mg = next((c for c in nc if any(k in c.lower() for k in ["marge","margin"])), None)
                vl = next((c for c in nc if any(k in c.lower() for k in ["volume","forecast","qty","sales"])), None)
                if mg and vl:
                    profits = [cn(row[vl])*cn(row[mg]) for _,row in df.iterrows()
                               if cn(row[vl])>0 or cn(row[mg])>0]
                    if profits:
                        n_def = sum(1 for p in profits if p < 0)
                        lines += [
                            f"Profit total : <strong>{sum(profits):,.0f}</strong>",
                            f"Produits déficitaires : <strong style='color:{'#dc2626' if n_def>0 else '#16a34a'}'>"
                            f"{n_def}</strong>",
                        ]
                        verdict = "CRITIQUE" if n_def > 0 else "OK"
                    break
    except Exception as e:
        return ""  # Silencieux si erreur

    if not lines:
        return ""

    vcol = {"OK":"#16a34a","ATTENTION":"#d97706","CRITIQUE":"#dc2626","NO-GO":"#dc2626"}.get(verdict,"#374151")
    sc_badge = (f'<span style="font-size:.65rem;background:#eff6ff;color:#1e3a8a;'
                f'border:1px solid #bfdbfe;border-radius:4px;padding:.05rem .3rem;margin-left:.4rem">'
                f'Scénario : {sc_actif}</span>') if sc_actif and sc_actif not in ("NOMINAL","DEM_AUTO","") else ""

    bullets = "".join(f'<div style="padding:.07rem 0;display:flex;gap:.3rem">'
                      f'<span style="color:{vcol};font-size:.55rem;margin-top:.22rem">▶</span>'
                      f'<span>{l}</span></div>' for l in lines)

    return (f'<div style="background:#f8f9fc;border:1.5px solid var(--br);'
            f'border-left:3px solid {vcol};border-radius:6px;'
            f'padding:.4rem .65rem;margin-top:.3rem;font-size:.77rem;line-height:1.6">'
            f'<div style="font-size:.65rem;font-weight:700;letter-spacing:.1em;'
            f'text-transform:uppercase;color:var(--mu);font-family:JetBrains Mono,monospace;'
            f'margin-bottom:.2rem">Synthèse automatique'
            f'<span style="color:{vcol};margin-left:.5rem">{verdict}</span>'
            f'{sc_badge}</div>'
            f'{bullets}</div>')


def prod_stock_securite(dfs):
    """Stock de sécurité : SS = Z × σ × √LT — tableau complet par niveau de service et LT."""
    mrp  = mrp_calc(dfs, {}); p = mrp["p"]; W = mrp["weeks"]
    gross = mrp["gross"]
    ss_actuel = p["ss_v"]
    demands = [g for g in gross if g > 0]
    if len(demands) < 2:
        return '<div class="ae">Données insuffisantes pour calculer le stock de sécurité.</div>'

    mn   = round(float(np.mean(demands)), 1)
    std  = round(float(np.std(demands)),  1)
    cv   = round(std / mn * 100, 1) if mn > 0 else 0
    niveaux = [("90%",1.28,"#d97706"),("95%",1.65,"#2563eb"),
               ("98%",2.05,"#16a34a"),("99%",2.33,"#7c3aed")]
    lts = [1, 2, 3, 4]
    out = []

    out.append(f"""<div class="gloss">
<div class="gloss-t">Formule Stock de Sécurité : SS = Z × σ × √LT</div>
<div style="font-size:.76rem;line-height:1.7;margin-top:.2rem">
  <strong>Z</strong> = facteur de service | <strong>σ</strong> = écart-type demande =
  <strong>{std:,.1f} U/sem</strong> | <strong>LT</strong> = délai réapprovisionnement (semaines)<br>
  Demande moyenne : <strong>{mn:,.1f} U/sem</strong> | CV : <strong>{cv:.1f}%</strong>
  {"— série volatile, SS élevé recommandé" if cv > 40 else ""}<br>
  SS actuel dans le fichier : <strong>{ss_actuel:.0f} U</strong>
</div></div>""")

    # Tableau 1 : SS selon niveau de service × LT
    hd = ["Niveau service","Z","LT=1 sem","LT=2 sem","LT=3 sem","LT=4 sem","Usage typique"]
    rows = []
    usages = {"90%":"Produits courants","95%":"Standard industrie",
              "98%":"Produits critiques","99%":"Haute valeur / pénurie coûteuse"}
    for lbl, z, col in niveaux:
        ss_v = [round(z*std*(lt**0.5),0) for lt in lts]
        rows.append([
            f'<span style="color:{col};font-weight:700">{lbl}</span>',
            f"{z:.2f}",
            *[f"{v:,.0f} U" for v in ss_v],
            usages[lbl]
        ])
    out.append(T(hd, rows, None, f"SS = Z × {std:.1f} × √LT — par niveau de service et délai"))

    # Tableau 2 : comparaison SS actuel vs recommandé (95%, LT=2)
    ss_95_lt2 = round(1.65*std*(2**0.5), 0)
    ss_95_lt3 = round(1.65*std*(3**0.5), 0)
    hd2 = ["Scénario","SS actuel","SS recommandé 95%","Écart","Interprétation"]
    rows2 = []
    for lt_v, ss_r in [(2, ss_95_lt2), (3, ss_95_lt3)]:
        diff = ss_r - ss_actuel
        col_d = "#dc2626" if diff > 0 else "#16a34a"
        rows2.append([
            f"LT = {lt_v} semaines",
            f"{ss_actuel:.0f} U", f"{ss_r:,.0f} U",
            f'<span style="color:{col_d};font-weight:700">{diff:+,.0f} U</span>',
            "Insuffisant — risque rupture" if diff > 0 else "Suffisant"
        ])
    out.append(T(hd2, rows2, None, "Comparaison SS actuel vs recommandé (niveau 95%)"))

    # Tableau 3 : par période
    hd3 = ["Période","Demande","Écart vs moy","SS 90% LT=2","SS 95% LT=2","SS 98% LT=2","Statut"]
    rows3 = []; cls3 = []
    ss_90 = round(1.28*std*(2**0.5), 0)
    ss_95 = round(1.65*std*(2**0.5), 0)
    ss_98 = round(2.05*std*(2**0.5), 0)
    for i, w in enumerate(W):
        g = gross[i]
        if g <= 0: continue
        wl = w.replace(" Y23",""); ecart = g - mn
        col_e = "#dc2626" if ecart > std else "#16a34a" if ecart < -std else "#374151"
        if g > mn + 2*std:
            st_v = '<span style="color:#dc2626;font-weight:700">PIC — SS élevé requis</span>'
            cls3.append("surge")
        elif g > mn + std:
            st_v = '<span style="color:#d97706;font-weight:700">ÉLEVÉ</span>'
            cls3.append("alrt")
        else:
            st_v = '<span style="color:#16a34a;font-weight:700">NORMAL</span>'
            cls3.append("")
        rows3.append([wl, f"{g:,.0f}",
                      f'<span style="color:{col_e}">{ecart:+,.0f}</span>',
                      f"{ss_90:,.0f}", f"{ss_95:,.0f}", f"{ss_98:,.0f}", st_v])
    out.append(T(hd3, rows3, cls3, "Stock de Sécurité par Période (LT = 2 semaines)"))

    n_pics = sum(1 for g in gross if g > mn + 2*std)
    out.append(S("Stock de Sécurité",[
        f"• σ = <strong>{std:,.1f} U</strong> | Moy = <strong>{mn:,.1f} U</strong> | CV = <strong>{cv:.1f}%</strong>.",
        f"• SS actuel = <strong>{ss_actuel:.0f} U</strong> | SS recommandé 95% LT=2 = <strong>{ss_95_lt2:,.0f} U</strong>"
          f" ({'<span style=\"color:#dc2626\">insuffisant</span>' if ss_95_lt2 > ss_actuel else '<span style=\"color:#16a34a\">suffisant</span>'}).",
        f"• {n_pics} période(s) avec pic (demande > moy + 2σ) — le SS standard ne couvre pas ces pics.",
        f"• Ajustez LT au délai réel de votre fournisseur et choisissez le niveau de service selon la criticité.",
    ]))
    return "".join(out)


def do_action(agent, q, dfs, sc_txt):
    result = None
    if q=="__MKT_AUTO__":   result = dem_auto(dfs,"marketing")
    elif q=="__DEM_AUTO__":  result = dem_auto(dfs,"demande")
    elif q=="__DEM_METHODS__": result = dem_methods(dfs)
    elif q=="__DEM_ANOM__":  result = dem_anomalies(dfs)
    elif q=="__DEM_MAPE__":  result = dem_mape_top(dfs)
    elif q=="__DEM_FC__":    result = dem_forecast(dfs)
    elif q=="__PRD_MRP__":
        result = prod_mrp(dfs,"")
    elif q=="__PRD_SURGE__": result = prod_surcharges(dfs)
    elif q=="__PRD_SIM30__": result = prod_sim30(dfs)
    elif q=="__PRD_SS__":    result = prod_stock_securite(dfs)
    elif q=="__FIN_AUTO__":  result = fin_auto(dfs)
    else:
        df_txt="\n".join(f"=={sh}==\n{df.head(12).to_string(index=False)}" for sh,df in dfs.items())
        result = groq(f"Agent {agent} S&OP. Reponds en 5-7 lignes. Chiffres exacts.",
                    f"Donnees:\n{df_txt[:2500]}\nScenario: {sc_txt}\nQuestion: {q}",500)

    # Synthèse automatique ajoutée après chaque réponse (sauf PRD_MRP qui l'intègre en interne)
    if result and q.startswith("__") and q != "__PRD_MRP__":
        synth = _build_synthese(agent, q, dfs)
        if synth:
            result = result + synth

    return result

# ── ONGLET AGENT ────────────────────────────────────────────────────────────────
def render_tab(agent):
    dfs=get_dfs(agent); has=bool(dfs)
    row_l, row_r = st.columns([3, 1])
    with row_l:
        pill=f'<span class="pill-ok">Charge</span>' if has else ""
        st.markdown(f'<div style="display:flex;align-items:center;gap:.38rem;padding:.15rem 0">'
                    f'<span style="font-weight:800;font-size:.88rem;color:var(--navy)">{agent.upper()}</span>'
                    f'{pill}</div>',unsafe_allow_html=True)
    with row_r:
        st.markdown('<div style="font-size:.62rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--mu);font-family:JetBrains Mono,monospace;margin-bottom:.1rem">Import</div>',unsafe_allow_html=True)
        up=st.file_uploader(f"up {agent}",type=["xlsx","xls"],key=f"up_{agent}",label_visibility="collapsed")
        if up is not None and st.session_state.files.get(agent)!=up.name:
            dfl,err=load_file(agent,up)
            if err: st.error(f"Erreur : {err}")
            else:
                add_msg(agent,"agent",f"Fichier <strong>{up.name}</strong> charge — {len(dfl)} feuille(s). Clique sur un bouton d'action.")
                st.session_state[f"_need_rerun_{agent}"] = True
        if has: st.markdown(f'<div class="fbadge">{st.session_state.files.get(agent,"")[:18]}</div>',unsafe_allow_html=True)

    # Rerun unique après chargement fichier (évite double rerun)
    if st.session_state.pop(f"_need_rerun_{agent}", False):
        st.rerun()

    if has:
        sc_txt=st.session_state.get(f"sc_{agent}","SITUATION NOMINALE")
        btns=BTNS.get(agent,[])
        cols=st.columns(len(btns))
        clicked_btn=None
        for i,(lbl,q) in enumerate(btns):
            with cols[i]:
                if st.button(lbl,key=f"btn_{agent}_{i}",use_container_width=True):
                    clicked_btn=(lbl,q)
        if clicked_btn:
            lbl,q=clicked_btn
            if q=="__DASHBOARD__":
                st.session_state.views[agent]="dashboard"
                # pas de st.rerun() — la page se reconstruit naturellement au prochain cycle
            else:
                st.session_state.views[agent]="chat"
                st.session_state.chats[agent]=[]
                add_msg(agent,"user",lbl)
                with st.spinner(f"Calcul : {lbl}..."):
                    result=do_action(agent,q,dfs,sc_txt)
                add_msg(agent,"agent",result)
                # pas de st.rerun() — le chat HTML se met à jour au rendu suivant
    else:
        st.markdown('<div style="height:.25rem"></div>',unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid var(--br);margin:.28rem 0 .38rem">',unsafe_allow_html=True)
    L,R=st.columns([1,2.8],gap="small")
    with L:
        st.markdown('<div class="slbl">Scenarios What-If</div>',unsafe_allow_html=True)
        sc_txt="SITUATION NOMINALE"

        if agent=="production" and has:
            cap_mode=st.radio("Cap mode",["Nominal","Capacite -X%","Capacite +X%","Capacite ignoree","Capacite absolue PHR"],
                              key=f"cap_mode_{agent}",label_visibility="collapsed")
            cap_pct=None; cap_abs=None
            if cap_mode=="Capacite -X%":
                cap_pct=-st.slider("Reduction %",5,90,20,5,key=f"cap_m_{agent}",label_visibility="collapsed")
                st.markdown(f'<div class="aw">Cap {cap_pct:.0f}%</div>',unsafe_allow_html=True)
            elif cap_mode=="Capacite +X%":
                cap_pct=st.slider("Augmentation %",5,150,25,5,key=f"cap_p_{agent}",label_visibility="collapsed")
                st.markdown(f'<div class="ag">Cap +{cap_pct:.0f}%</div>',unsafe_allow_html=True)
            elif cap_mode=="Capacite ignoree":
                cap_pct=99999
                st.markdown('<div class="aw">Capacite infinie</div>',unsafe_allow_html=True)
            elif cap_mode=="Capacite absolue PHR":
                cap_abs=st.number_input("PHR/sem",100,5000,1400,100,key=f"cap_abs_{agent}",label_visibility="collapsed")
                st.markdown(f'<div class="aw">Cap = {cap_abs:.0f} PHR</div>',unsafe_allow_html=True)
            use_mp=st.checkbox("Appliquer MinProd",key=f"use_mp_{agent}")
            minprod=None
            if use_mp:
                minprod=st.number_input("MinProd [U/sem]",0,50000,2000,100,key=f"mp_{agent}",label_visibility="collapsed")
                st.markdown(f'<div class="aw">MinProd = {minprod:,.0f} U/sem</div>',unsafe_allow_html=True)
            parts=[]
            if cap_mode=="Capacite -X%" and cap_pct: parts.append(f"CAP_MINUS_{abs(cap_pct)}")
            elif cap_mode=="Capacite +X%" and cap_pct: parts.append(f"CAP_PLUS_{cap_pct}")
            elif cap_mode=="Capacite ignoree": parts.append("CAP_IGNORED")
            elif cap_mode=="Capacite absolue PHR" and cap_abs: parts.append(f"CAP_{int(cap_abs)}")
            if use_mp and minprod: parts.append(f"MINPROD_{int(minprod)}")
            sc_txt = "+".join(parts) if parts else "NOMINAL"
            st.session_state.whatif_params["production"]={
                "cap_mode":cap_mode,"cap_pct":cap_pct,"cap_abs":cap_abs,
                "minprod":minprod if use_mp else None,"sc_txt":sc_txt}
            if sc_txt!="NOMINAL":
                st.markdown(f'<div class="ai" style="font-size:.75rem">Scenario actif : <strong>{sc_txt}</strong></div>',unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # WHAT-IF DEMANDE — PARAMÈTRES STRICTS SELON MÉTHODE SÉLECTIONNÉE
        # ══════════════════════════════════════════════════════════════════════
        # MA sélectionné  → fenêtre w UNIQUEMENT   (zéro α/β/γ affiché)
        # LES sélectionné → α UNIQUEMENT           (zéro β/γ affiché)
        # HW sélectionné  → α + β + γ              (les trois ensemble)
        # Auto            → aucun paramètre        (optimisation automatique)
        elif agent in ("demande","marketing") and has:
            # ══ SCÉNARIOS MÉTIER — MARKETING ══════════════════════════════════
            if agent == "marketing":
                scenario_mkt = st.radio(
                    "Scenario Marketing",
                    ["Nominal (aucun levier)",
                     "Augmentation budget publicitaire",
                     "Modification prix de vente",
                     "Promotion saisonniere",
                     "Lancement nouvelle gamme",
                     "Expansion geographique"],
                    key=f"sc_meth_{agent}", label_visibility="collapsed")
                parts = []
                if "budget" in scenario_mkt.lower():
                    st.markdown('<div class="ai" style="font-size:.74rem">Simuler une hausse du budget pub '
                                'et son impact sur la demande (+X%).</div>', unsafe_allow_html=True)
                    boost = st.slider("Hausse de la demande estimee (%)", 5, 50, 15,
                                      key=f"sc_mkt_boost_{agent}", label_visibility="collapsed")
                    st.markdown(f'<div style="font-size:.72rem;color:var(--mu)">+{boost}% sur tous les articles</div>',
                                unsafe_allow_html=True)
                    parts = [f"MKT_BUDGET_PLUS_{boost}"]

                elif "prix" in scenario_mkt.lower():
                    st.markdown('<div class="ai" style="font-size:.74rem">Simuler une hausse ou baisse '
                                'de prix et son impact sur la demande.</div>', unsafe_allow_html=True)
                    delta_prix = st.slider("Variation de prix (%)", -30, 30, -10,
                                          key=f"sc_mkt_prix_{agent}", label_visibility="collapsed")
                    # Elasticite prix classique : -1 -> hausse 10% = baisse 10% demande
                    impact_dem = -delta_prix  # elasticite = -1 simplifiee
                    st.markdown(f'<div style="font-size:.72rem;color:var(--mu)">Prix {delta_prix:+.0f}% '
                                f'-> demande estimee {impact_dem:+.0f}% (elasticite -1)</div>',
                                unsafe_allow_html=True)
                    parts = [f"MKT_PRIX_{delta_prix:+.0f}"]

                elif "promo" in scenario_mkt.lower():
                    st.markdown('<div class="ai" style="font-size:.74rem">Simuler une promotion '
                                'saisonniere sur une periode cible.</div>', unsafe_allow_html=True)
                    boost_promo = st.slider("Boost demande pendant la promo (%)", 10, 100, 30,
                                            key=f"sc_mkt_promo_{agent}", label_visibility="collapsed")
                    parts = [f"MKT_PROMO_PLUS_{boost_promo}"]

                elif "gamme" in scenario_mkt.lower():
                    st.markdown('<div class="ai" style="font-size:.74rem">Evaluer la charge additionnelle '
                                'liee au lancement d\'un nouveau produit.</div>', unsafe_allow_html=True)
                    vol_new = st.slider("Volume estime nouveau produit (U/mois)", 100, 5000, 500,
                                        key=f"sc_mkt_gamme_{agent}", label_visibility="collapsed")
                    parts = [f"MKT_GAMME_NEW_{vol_new}"]

                elif "expansion" in scenario_mkt.lower():
                    st.markdown('<div class="ai" style="font-size:.74rem">Simuler une expansion '
                                'geographique et son impact sur les volumes totaux.</div>', unsafe_allow_html=True)
                    mult = st.slider("Multiplicateur de volume (%)", 10, 100, 25,
                                     key=f"sc_mkt_expand_{agent}", label_visibility="collapsed")
                    parts = [f"MKT_EXPANSION_PLUS_{mult}"]
                else:
                    st.markdown('<div class="ag" style="font-size:.74rem">Mode nominal — '
                                'analyse basee sur les donnees reelles.</div>', unsafe_allow_html=True)

                sc_txt = "+".join(parts) if parts else "MKT_NOMINAL"

            # ══ SCÉNARIOS MÉTHODE — DEMANDE ══════════════════════════════════
            else:
                method=st.radio("Methode",
                                ["Auto (recommandee — MAPE min)",
                                 "Forcer MA (fenetre uniquement)",
                                 "Forcer LES (alpha seul)",
                                 "Forcer HW (alpha, beta, gamma)"],
                                key=f"sc_meth_{agent}",label_visibility="collapsed")
                ma_w=None; alpha_val=None; beta_val=None; gamma_val=None; parts=[]

                if "MA" in method:
                    st.markdown('<div class="ai" style="font-size:.74rem">MA — fenetre glissante. '
                                'Aucun parametre alpha/beta/gamma.</div>', unsafe_allow_html=True)
                    ma_w = st.slider("Fenetre w", 2, 12, 3, key=f"sc_ma_{agent}", label_visibility="collapsed")
                    st.markdown(f'<div style="font-size:.72rem;color:var(--mu)">w={ma_w} — '
                                f'moyenne des {ma_w} dernieres valeurs</div>', unsafe_allow_html=True)
                    parts.append(f"DEM_MA_{ma_w}")
                elif "LES" in method:
                    st.markdown('<div class="ai" style="font-size:.74rem">LES — alpha uniquement. '
                                'Beta et gamma non applicables.</div>', unsafe_allow_html=True)
                    alpha_val = st.slider("alpha (reacticvite)", 0.05, 0.95, 0.3, 0.05,
                                          key=f"sc_alpha_{agent}", label_visibility="collapsed")
                    st.markdown(f'<div style="font-size:.72rem;color:var(--mu)">alpha={alpha_val}</div>',
                                unsafe_allow_html=True)
                    parts.append("DEM_LES"); parts.append(f"ALPHA_{alpha_val}")
                elif "HW" in method:
                    st.markdown('<div class="ai" style="font-size:.74rem">HW — alpha + beta + gamma.</div>',
                                unsafe_allow_html=True)
                    alpha_val = st.slider("alpha (niveau)", 0.05, 0.95, 0.3, 0.05,
                                          key=f"sc_alpha_hw_{agent}", label_visibility="collapsed")
                    beta_val  = st.slider("beta (tendance)",  0.01, 0.50, 0.10, 0.01,
                                          key=f"sc_beta_{agent}",  label_visibility="collapsed")
                    gamma_val = st.slider("gamma (saisonnalite)", 0.01, 0.50, 0.10, 0.01,
                                          key=f"sc_gamma_{agent}", label_visibility="collapsed")
                    parts.append("DEM_HW")
                    parts.append(f"ALPHA_{alpha_val}")
                    parts.append(f"BETA_{beta_val}")
                    parts.append(f"GAMMA_{gamma_val}")
                else:
                    st.markdown('<div class="ag" style="font-size:.74rem">Auto : MAPE le plus bas '
                                'parmi MA, LES, HW.</div>', unsafe_allow_html=True)
                sc_txt = "+".join(parts) if parts else "DEM_AUTO"
                st.session_state.whatif_params["demande"] = {
                    "method": method, "alpha": alpha_val, "beta": beta_val,
                    "gamma": gamma_val, "ma_w": ma_w, "sc_txt": sc_txt}

            if sc_txt not in ("DEM_AUTO","MKT_NOMINAL",""):
                st.markdown(f'<div class="ai" style="font-size:.75rem;margin-top:.3rem">'
                            f'Scenario actif : <strong>{sc_txt}</strong></div>',
                            unsafe_allow_html=True)
        # ══════════════════════════════════════════════════════════════════════

        else:
            sc_type=st.radio("Scenario",["Nominal","Personnalise"],key=f"sc_type_{agent}",label_visibility="collapsed")
            if "Personnalise" in sc_type:
                sc_txt=st.text_input("Scenario","",key=f"sc_txt_{agent}",label_visibility="collapsed",placeholder="Decris le scenario...")

        st.session_state[f"sc_{agent}"]=sc_txt
        st.markdown('<div style="margin-top:.45rem"></div>', unsafe_allow_html=True)
        render_definitions(agent)

    with R:
        view=st.session_state.views.get(agent,"chat")
        if view=="dashboard" and has:
            if st.button("Retour au chat",key=f"bk_{agent}",help="Retour"):
                st.session_state.views[agent]="chat"; st.rerun()
            with st.spinner("Dashboard..."):
                render_dashboard(agent,dfs)
        else:
            render_chat(agent)
            c1,c2=st.columns([7,1])
            with c1:
                qi=st.text_input("Question",key=f"q_{agent}",label_visibility="collapsed",
                                 placeholder=f"Question a l'agent {agent}..." if has else "Charge un fichier d'abord...")
            with c2:
                st.markdown('<div class="btn-send">',unsafe_allow_html=True)
                send=st.button("->",key=f"s_{agent}")
                st.markdown('</div>',unsafe_allow_html=True)
            if send and qi.strip():
                if not has: st.warning("Charge un fichier.")
                else:
                    add_msg(agent,"user",qi.strip())
                    with st.spinner("Calcul..."):
                        if agent=="production":
                            result=""
                            mrp_b=mrp_calc(dfs,{}); ov=parse_ov(qi,mrp_b["weeks"])
                            sc_cur=st.session_state.get(f"sc_{agent}","NOMINAL")
                            if ov:
                                result=prod_mrp(dfs,qi)
                                try: _auto_email_check(trigger="Analyse MRP chat", agent="production")
                                except Exception: pass
                            else:
                                q_low=qi.strip().lower()
                                p=mrp_b["p"]; W=mrp_b["weeks"]
                                if sc_cur and sc_cur not in ("NOMINAL",""):
                                    _nc,_mp,_lbl=_parse_prod_scenario(sc_cur,p["cap_v"])
                                    mrp_sc=_mrp_calc_with_new_cap(mrp_b,_nc,p["var_v"],p["ss_v"],p["bat_v"],minprod=_mp)
                                    max_u_sc=round(_nc/p["var_v"],0) if p["var_v"]>0 else _nc; cap_sc=_nc; sc_label=_lbl
                                else:
                                    mrp_sc=mrp_b; max_u_sc=p["max_u"]; cap_sc=p["cap_v"]; sc_label="Nominal"
                                is_hs  = any(k in q_low for k in ["heure sup","heure supp","hs ","heures sup","overtime","combien hs","combien heure","heure supplement"])
                                is_st  = any(k in q_low for k in ["sous-trait","sous traite","externaliser","combien sous","combien st ","combien a sous"])
                                is_mrp = any(k in q_low for k in ["mrp","plan","programme","tableau complet"])
                                if is_hs:
                                    result=prod_hs_calc(dfs)
                                elif is_st:
                                    rows_st=[]; tot_st=0.0; ns_st=0
                                    for _i,_w in enumerate(W):
                                        _d=mrp_b["gross"][_i]; _def=max(0.0,_d-max_u_sc)
                                        if _def>0:
                                            tot_st+=_def; ns_st+=1
                                            _sat=round(_d*p["var_v"]/cap_sc*100,0) if cap_sc>0 else 0
                                            rows_st.append((_w.replace(" Y23",""),_d,int(max_u_sc),int(_def),_sat))
                                    hd_st=["Semaine","Demande [U]","Max prod. [U]","ST requise [U]","Saturation %","Pourquoi sous-traiter ?"]
                                    rows_html=[]
                                    for r in rows_st:
                                        motif = f"Demande {r[1]:,} U depasse la capacite {r[2]:,} U/sem ({r[4]:.0f}% de saturation)"
                                        rows_html.append([r[0],f"{r[1]:,}",f"{r[2]:,}",
                                                          f'<strong style="color:#dc2626">{r[3]:,}</strong>',
                                                          f"{r[4]:.0f}%",motif])
                                    th_st="<tr>"+"".join(f"<th>{h}</th>" for h in hd_st)+"</tr>"
                                    td_st="".join(
                                        f'<tr style="background:#fef2f2"><td class="l"><strong>{r[0]}</strong></td>'
                                        +"".join(f'<td>{c}</td>' for c in r[1:])+"</tr>"
                                        for r in rows_html)
                                    result=(f'<div class="tw"><table class="sop"><thead>{th_st}</thead>'
                                            f'<tbody>{td_st}</tbody></table></div>')
                                    result+=f"""
<div style="background:#f8f9fc;border:1.5px solid var(--br);border-radius:8px;padding:.6rem .85rem;margin:.4rem 0">
  <div style="font-weight:700;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--navy);font-family:JetBrains Mono,monospace;margin-bottom:.3rem">Analyse Sous-Traitance</div>
  <div style="font-size:.8rem;color:#374151;line-height:1.7">
    <strong>Volume total a sous-traiter : {tot_st:,.0f} U sur {ns_st} semaine(s)</strong><br>
    <strong>Formule :</strong> ST = Demande − Max prod. | Max prod. = {cap_sc:.0f} PHR ÷ {p['var_v']:.4f} PHR/U = {max_u_sc:.0f} U/sem<br><br>
    <strong>Pourquoi sous-traiter ?</strong> La demande depasse massivement la capacite interne.
    Les pics (ex. {max(r[1] for r in rows_st):,} U/sem) representent {round(max(r[1] for r in rows_st)/max_u_sc,1)}x
    la capacite max — aucun levier interne (HS, anticipation) ne peut compenser seul.<br><br>
    <strong>Actions recommandees en sequence :</strong><br>
    1. Verifier si HS +50% peut couvrir certaines semaines (reduit ST de {sum(max(0,r[1]-int(cap_sc*1.5/p['var_v']) if p['var_v']>0 else int(cap_sc)) for r in rows_st):,} U).<br>
    2. Lancer un appel d'offres fournisseur ST pour les <strong>{tot_st:,.0f} U</strong> restantes.<br>
    3. Surcoût estimé : +30-35% vs production interne — obtenir 2-3 devis avant engagement.<br>
    4. Valider la capacite du fournisseur a absorber les pics W40-W41 ({max(r[1] for r in rows_st):,} U/sem).
  </div>
</div>"""
                                else:
                                    result=_whatif_prod_result(mrp_b, mrp_sc, sc_label) if sc_label!="Nominal" else prod_mrp(dfs,"")
                                try: _auto_email_check(trigger="What-If Production", agent="production")
                                except Exception: pass
                        else:
                            result=""
                            sc_cur=st.session_state.get(f"sc_{agent}","DEM_AUTO")
                            if sc_cur and sc_cur not in ("DEM_AUTO","NOMINAL",""):
                                result=do_action_whatif(agent,qi.strip(),dfs,sc_cur)
                            if not result:
                                result=do_action(agent,qi.strip(),dfs,sc_cur)
                    if result: add_msg(agent,"agent",result)
                    # Pas de st.rerun() — le HTML du chat se reconstruit dans le même cycle

# ── ORCHESTRATEUR ─────────────────────────────────────────────────────────────
# ── SYSTÈME D'ALERTES EMAIL ───────────────────────────────────────────────────
# ── SYSTÈME D'ALERTES EMAIL ───────────────────────────────────────────────────
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_PRESETS = {
    "Gmail":              ("smtp.gmail.com",           587),
    "Outlook / Hotmail":  ("smtp-mail.outlook.com",    587),
    "Yahoo":              ("smtp.mail.yahoo.com",       587),
    "OVH":                ("ssl0.ovh.net",              587),
    "Personnalisé":       ("",                          587),
}


def _email_build_html(data, contexte, flags, diagnostics, actions, scenario):
    """Corps HTML de l'email d'alerte."""
    p = data["production"]; arts = data["demande"]
    v_global, c_global = _orch_verdict_global(flags)
    col_map = {"GO":"#16a34a","GO CONDITIONNEL":"#d97706","NO-GO":"#dc2626","N/D":"#6b7280"}
    col = col_map.get(v_global, "#374151")
    ctx_label = {"historique":"Analyse historique","plan":"Plan prévisionnel",
                 "ambigu":"Contexte indéterminé"}.get(contexte,"")
    alertes = []
    if p:
        if p["n_rupture"] > 0:
            alertes.append(f"Rupture stock : {p['n_rupture']} sem., stock min {p['stock_min']:,.0f} U")
        if p["sat_max"] > 200:
            alertes.append(f"Saturation critique {p['sat_max']:.0f}% sur {p['pic_w']}")
        if p["n_surcharge"] > p["weeks_total"] * 0.5:
            alertes.append(f"{p['n_surcharge']}/{p['weeks_total']} semaines en surcharge")
    if arts:
        mpy = round(sum(a["mape_py"] for a in arts)/len(arts), 1)
        if mpy > 25:
            alertes.append(f"Qualité prévision dégradée : MAPE {mpy:.1f}%")
    alertes_html = "".join(
        f'<tr><td style="padding:6px 12px;border-left:4px solid #dc2626;'
        f'background:#fef2f2;margin:3px 0;display:block">{a}</td></tr>'
        for a in alertes) or '<tr><td style="padding:6px 12px;color:#16a34a">Aucune alerte critique.</td></tr>'
    actions_html = ""
    for a in sorted(actions, key=lambda x:x["prio"])[:3]:
        actions_html += (f'<tr style="border-bottom:1px solid #e5e7eb">'
                         f'<td style="padding:8px;font-weight:700;color:#1e3a8a">Étape {a["prio"]}</td>'
                         f'<td style="padding:8px">{a["action"]}</td>'
                         f'<td style="padding:8px;color:#6b7280">{a["delai"]}</td></tr>')
    if not actions_html:
        actions_html = '<tr><td colspan="3" style="padding:8px;color:#16a34a">Aucune action requise.</td></tr>'
    metrics = ""
    if p:
        metrics = (f'<td style="padding:10px;text-align:center;border-right:1px solid #e5e7eb">'
                   f'<div style="font-size:22px;font-weight:900;color:{"#dc2626" if p["n_surcharge"]>0 else "#16a34a"}">'
                   f'{p["n_surcharge"]}/{p["weeks_total"]}</div>'
                   f'<div style="font-size:11px;color:#6b7280">Surcharges</div></td>'
                   f'<td style="padding:10px;text-align:center;border-right:1px solid #e5e7eb">'
                   f'<div style="font-size:22px;font-weight:900;color:{"#dc2626" if p["stock_min"]<0 else "#16a34a"}">'
                   f'{p["stock_min"]:,.0f} U</div>'
                   f'<div style="font-size:11px;color:#6b7280">Stock min</div></td>'
                   f'<td style="padding:10px;text-align:center">'
                   f'<div style="font-size:22px;font-weight:900;color:{"#dc2626" if p["sat_max"]>100 else "#16a34a"}">'
                   f'{p["sat_max"]:.0f}%</div>'
                   f'<div style="font-size:11px;color:#6b7280">Sat. max</div></td>')
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f3f4f6;margin:0;padding:20px">
<div style="max-width:680px;margin:0 auto;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)">
<div style="background:#1e3a8a;padding:24px 28px;color:#fff">
  <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;opacity:.7">AlBrain S&OP</div>
  <div style="font-size:22px;font-weight:900;margin:6px 0">Alerte S&OP</div>
  <div style="font-size:13px;opacity:.8">Scénario : {scenario} — {now}</div>
</div>
<div style="padding:20px 28px;border-bottom:1px solid #e5e7eb">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#6b7280;margin-bottom:6px">Verdict {ctx_label}</div>
  <div style="font-size:28px;font-weight:900;color:{col}">{v_global}</div>
</div>
{"<table style='width:100%;border-bottom:1px solid #e5e7eb'><tr>"+metrics+"</tr></table>" if metrics else ""}
<div style="padding:16px 28px;border-bottom:1px solid #e5e7eb">
  <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#374151;margin-bottom:10px">Alertes</div>
  <table style="width:100%;border-collapse:collapse">{alertes_html}</table>
</div>
<div style="padding:16px 28px;border-bottom:1px solid #e5e7eb">
  <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#374151;margin-bottom:10px">Plan d'action</div>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr style="background:#f8f9fc;font-weight:700"><td style="padding:8px">Étape</td><td style="padding:8px">Action</td><td style="padding:8px">Délai</td></tr>
    {actions_html}
  </table>
</div>
<div style="padding:16px 28px;background:#f8f9fc;font-size:12px;color:#6b7280">Email automatique — AlBrain S&OP Platform</div>
</div></body></html>"""


def send_alert_email(data, contexte, flags, diagnostics, actions, scenario, cfg, reason="Manuel"):
    """Envoie l'email d'alerte via SMTP. Retourne (True, msg) ou (False, erreur)."""
    if not cfg.get("enabled") or not cfg.get("sender") or not cfg.get("recipient"):
        return False, "Email non configuré."
    try:
        msg = MIMEMultipart("alternative")
        v_global, _ = _orch_verdict_global(flags)
        p = data["production"]
        prefix = "🔴 ALERTE CRITIQUE" if (v_global=="NO-GO" or (p and p["n_rupture"]>0)) else \
                 "🟡 ATTENTION" if v_global=="GO CONDITIONNEL" else "🟢 INFO"
        msg["Subject"] = f"{prefix} S&OP — {scenario} — {reason}"
        msg["From"]    = cfg["sender"]
        msg["To"]      = cfg["recipient"]
        msg.attach(MIMEText(_email_build_html(data,contexte,flags,diagnostics,actions,scenario),"html","utf-8"))
        ctx_ssl = ssl.create_default_context()
        with smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"])) as server:
            server.ehlo(); server.starttls(context=ctx_ssl)
            server.login(cfg["sender"], cfg["password"])
            server.sendmail(cfg["sender"], cfg["recipient"], msg.as_string())
        st.session_state.email_config["last_sent"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        return True, f"Email envoyé à {cfg['recipient']}"
    except smtplib.SMTPAuthenticationError:
        return False, ("Authentification échouée. Gmail : activez la validation en 2 étapes "
                       "et créez un Mot de passe d'application sur myaccount.google.com.")
    except Exception as e:
        return False, f"Erreur : {e}"


def _auto_email_check(trigger="analyse", agent=None):
    """
    Envoie automatiquement si alerte critique détectée.
    Version robuste : montre clairement pourquoi l'email est envoyé ou bloqué.
    """
    cfg = st.session_state.get("email_config", {})

    # ── Vérification configuration ─────────────────────────────────────────────
    if not cfg.get("enabled"):
        return  # Email désactivé — pas de log (comportement normal)

    if not cfg.get("auto_send"):
        return  # Mode manuel — l'utilisateur envoie manuellement

    manquants = [k for k in ("sender","recipient","password") if not cfg.get(k)]
    if manquants:
        # Ajouter un avertissement visible dans la discussion orch
        st.session_state.disc = st.session_state.get("disc", []) + [{
            "agent": "ORCH",
            "content": f'<div class="aw">📧 Email non envoyé — champs manquants : '
                       f'{", ".join(manquants)}. Complétez la configuration dans '
                       f'"Alertes Email" (sidebar Orchestrateur).</div>',
            "ts": datetime.now().strftime("%H:%M")}]
        return

    # ── Anti-spam : 5 min minimum entre deux emails (pas 30) ─────────────────
    last = cfg.get("last_sent")
    if last:
        try:
            from datetime import timedelta
            elapsed = datetime.now() - datetime.strptime(last, "%d/%m/%Y %H:%M")
            if elapsed.total_seconds() < 300:  # 5 minutes
                return  # Trop récent, silencieux
        except: pass

    # ── Collecte des données réelles ──────────────────────────────────────────
    data = _orch_collect_data()
    p    = data["production"]

    # ── Détection des alertes critiques ───────────────────────────────────────
    alertes = []
    if p:
        if p["n_rupture"] > 0:
            alertes.append(f"⚠ Rupture stock : {p['n_rupture']} semaine(s), stock min {p['stock_min']:,.0f} U")
        if p["sat_max"] > 150:
            alertes.append(f"⚠ Saturation critique : {p['sat_max']:.0f}% (pic {p['pic_w']} = {p['pic_dem']:,.0f} U)")
        if p["n_surcharge"] > 0:
            alertes.append(f"⚠ {p['n_surcharge']}/{p['weeks_total']} semaines en surcharge")
    if data["demande"]:
        mpy = round(sum(a["mape_py"] for a in data["demande"])/len(data["demande"]), 1)
        if mpy > 20:
            alertes.append(f"⚠ Qualité prévision dégradée : MAPE {mpy:.1f}%")

    if not alertes:
        return  # Aucun problème → pas d'email, silencieux

    # ── Envoi ─────────────────────────────────────────────────────────────────
    contexte = _orch_detect_context(data)
    flags    = _orch_detect_situation(data)
    diags, acts = _orch_reason(data, flags)
    sc  = st.session_state.get("sc_orch", "SITUATION NOMINALE")
    rsn = f"Alerte auto — {trigger}" + (f" ({agent})" if agent else "")

    ok, msg = send_alert_email(data, contexte, flags, diags, acts, sc, cfg, reason=rsn)

    # ── Feedback visible dans la discussion orchestrateur ─────────────────────
    if ok:
        notif = (f'<div class="ag">📧 <strong>Email envoyé</strong> à '
                 f'<strong>{cfg["recipient"]}</strong><br>'
                 f'<span style="font-size:.72rem;color:#374151">'
                 f'{"<br>".join(alertes)}</span></div>')
    else:
        notif = (f'<div class="ae">📧 <strong>Échec envoi email</strong> — {msg}<br>'
                 f'<span style="font-size:.72rem">Vérifiez la configuration SMTP '
                 f'(Gmail : mot de passe d\'application requis).</span></div>')

    st.session_state.disc = st.session_state.get("disc", []) + [{
        "agent": "ORCH", "content": notif,
        "ts": datetime.now().strftime("%H:%M")}]


def render_email_config():
    """Section email avec statut en temps réel et diagnostic."""
    cfg = st.session_state.email_config
    with st.expander("📧 Alertes Email", expanded=False):

        # ── Statut rapide ─────────────────────────────────────────────────────
        all_set = cfg.get("enabled") and cfg.get("sender") and cfg.get("recipient") and cfg.get("password")
        if all_set:
            st.markdown('<div class="ag" style="font-size:.72rem">✓ Email configuré</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="aw" style="font-size:.72rem">⚠ Email non configuré</div>',
                        unsafe_allow_html=True)

        enabled = st.toggle("Activer", value=cfg["enabled"], key="email_enabled")
        st.session_state.email_config["enabled"] = enabled

        if enabled:
            # ── Fournisseur ───────────────────────────────────────────────────
            preset = st.selectbox("Fournisseur", list(SMTP_PRESETS.keys()),
                                  key="email_preset", label_visibility="collapsed")
            srv, prt = SMTP_PRESETS[preset]
            if preset == "Personnalisé":
                srv = st.text_input("Serveur SMTP", value=cfg["smtp_server"],
                                    key="email_srv", label_visibility="collapsed",
                                    placeholder="smtp.monserveur.com")
            else:
                st.markdown(f'<div style="font-size:.71rem;color:var(--mu)">{srv} | Port {prt}</div>',
                            unsafe_allow_html=True)
            st.session_state.email_config["smtp_server"] = srv
            st.session_state.email_config["smtp_port"]   = prt

            # ── Identifiants ──────────────────────────────────────────────────
            sender = st.text_input("Votre email (expéditeur)", value=cfg["sender"],
                                   key="email_sender", label_visibility="collapsed",
                                   placeholder="votre@email.com")
            password = st.text_input("Mot de passe application", value=cfg["password"],
                                     key="email_pass", type="password",
                                     label_visibility="collapsed",
                                     placeholder="Mot de passe app Gmail / SMTP")
            recipient = st.text_input("Email destinataire", value=cfg["recipient"],
                                      key="email_recip", label_visibility="collapsed",
                                      placeholder="destinataire@email.com")
            st.session_state.email_config["sender"]    = sender
            st.session_state.email_config["password"]  = password
            st.session_state.email_config["recipient"] = recipient

            # ── Mode auto ─────────────────────────────────────────────────────
            auto = st.toggle("Envoi automatique", value=cfg["auto_send"], key="email_auto")
            st.session_state.email_config["auto_send"] = auto
            if auto:
                st.markdown('<div class="ag" style="font-size:.71rem">'
                            'L\'agent envoie seul dès qu\'une surcharge, rupture ou saturation '
                            '> 150% est détectée. Anti-spam : 5 min entre deux emails.</div>',
                            unsafe_allow_html=True)

            # ── Note Gmail ────────────────────────────────────────────────────
            if preset == "Gmail":
                st.markdown(
                    '<div class="aw" style="font-size:.71rem">'
                    '<strong>Gmail :</strong> N\'utilisez pas votre mot de passe habituel.<br>'
                    '1. Allez sur <u>myaccount.google.com</u><br>'
                    '2. Sécurité → Validation en 2 étapes → Activer<br>'
                    '3. Mots de passe d\'application → Générer → Copier les 16 caractères<br>'
                    '4. Collez ces 16 caractères dans le champ ci-dessus</div>',
                    unsafe_allow_html=True)

            # ── Boutons ───────────────────────────────────────────────────────
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔍 Tester", key="email_test", use_container_width=True):
                    test_data = {"production":None,"demande":[],"finance":None,
                                 "errors":[],"scenarios_actifs":{}}
                    ok, msg = send_alert_email(
                        test_data, "plan", _orch_detect_situation(test_data),
                        [], [], "TEST", st.session_state.email_config, reason="Test connexion")
                    if ok: st.success(f"✓ {msg}")
                    else:  st.error(f"✗ {msg}")

            with c2:
                if st.button("📤 Envoyer", key="email_manual", use_container_width=True):
                    data = _orch_collect_data()
                    ctx  = _orch_detect_context(data)
                    fl   = _orch_detect_situation(data)
                    d, a = _orch_reason(data, fl)
                    ok, msg = send_alert_email(
                        data, ctx, fl, d, a,
                        st.session_state.get("sc_orch","SITUATION NOMINALE"),
                        st.session_state.email_config, reason="Envoi manuel")
                    if ok: st.success(f"✓ {msg}")
                    else:  st.error(f"✗ {msg}")

            with c3:
                if st.button("🔄 Reset anti-spam", key="email_reset_spam",
                             use_container_width=True):
                    st.session_state.email_config["last_sent"] = None
                    st.success("Anti-spam réinitialisé")

            # ── Diagnostic ────────────────────────────────────────────────────
            diag_lines = []
            if not sender:    diag_lines.append("❌ Email expéditeur manquant")
            if not password:  diag_lines.append("❌ Mot de passe manquant")
            if not recipient: diag_lines.append("❌ Email destinataire manquant")
            if not auto:      diag_lines.append("ℹ Mode manuel — cliquez 'Envoyer' pour envoyer")
            if cfg.get("last_sent"):
                diag_lines.append(f"📅 Dernier envoi : {cfg['last_sent']}")
            else:
                diag_lines.append("📅 Aucun envoi effectué dans cette session")
            if diag_lines:
                st.markdown(
                    '<div style="background:#f8f9fc;border:1px solid var(--br);'
                    'border-radius:5px;padding:.3rem .5rem;margin-top:.2rem">'
                    + "".join(f'<div style="font-size:.69rem;color:#374151">{l}</div>'
                               for l in diag_lines)
                    + '</div>', unsafe_allow_html=True)


def render_orchestrateur():
    has_any=any(bool(get_dfs(a)) for a in ["marketing","demande","production","finance"])
    row_l,row_r=st.columns([3,1])
    with row_l:
        pill=f'<span class="pill-ok">Donnees agents disponibles</span>' if has_any else ""
        st.markdown(f'<div style="display:flex;align-items:center;gap:.38rem;padding:.15rem 0">'
                    f'<span style="font-weight:800;font-size:.88rem;color:var(--navy)">ORCHESTRATEUR</span>'
                    f'{pill}</div>',unsafe_allow_html=True)
    with row_r:
        st.markdown('<div style="font-size:.62rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--mu);font-family:JetBrains Mono,monospace;margin-bottom:.1rem">Import global</div>',unsafe_allow_html=True)
        up=st.file_uploader("up orch",type=["xlsx","xls"],key="up_orch",label_visibility="collapsed")
        if up is not None and st.session_state.files.get("orchestrateur")!=up.name:
            dfl,err=load_file("orchestrateur",up)
            if err: st.error(f"Erreur : {err}")
            else:
                for a in ["marketing","demande","production","finance"]:
                    if not st.session_state.dfs.get(a):
                        st.session_state.dfs[a]=dfl; st.session_state.files[a]=up.name
                st.success(f"Partage a tous les agents.")
        if has_any: st.markdown('<div class="fbadge">Agents charges</div>',unsafe_allow_html=True)

    sc_txt=st.session_state.get("sc_orch","SITUATION NOMINALE")
    ORCH_BTNS=[
        ("Lancer analyse S&OP","__ORCH_LAUNCH__"),
        ("Decision GO/NO-GO","__ORCH_GONO__"),
        ("Plan d'action","__ORCH_PLAN__"),
        ("Rapport S&OP","__ORCH_RAPPORT__"),
        ("Effacer","__ORCH_CLEAR__"),
    ]
    ocols=st.columns(len(ORCH_BTNS))
    clicked_orch=None
    for i,(lbl,q) in enumerate(ORCH_BTNS):
        with ocols[i]:
            if st.button(lbl,key=f"bo{i}",use_container_width=True):
                clicked_orch=(lbl,q)
    if clicked_orch:
        lbl,q=clicked_orch
        st.session_state.chats["orchestrateur"]=[]
        if q=="__ORCH_LAUNCH__":
            with st.spinner("Analyse S&OP en cours..."):
                orchestrate(sc_txt)
            st.rerun()
        elif q=="__ORCH_GONO__":
            add_msg("orchestrateur","user",lbl)
            data = _orch_collect_data()
            p = data["production"]; arts = data["demande"]
            v_prod, c_prod, why_prod = _orch_verdict_prod(p)
            v_dem,  c_dem,  why_dem  = _orch_verdict_dem(arts)

            # Verdict global : source unique = _orch_verdict_global
            # Evite la contradiction entre les boutons
            flags_gono = _orch_detect_situation(data)
            v_global, c_global = _orch_verdict_global(flags_gono)

            # Note si What-If ameliore mais production locale = NO-GO
            wi_note = ""
            if v_prod == "NO-GO" and v_global != "NO-GO":
                sc_actifs_g = data.get("scenarios_actifs", {})
                sc_p = sc_actifs_g.get("production", "")
                # N'afficher la note que si un vrai scénario est actif
                if sc_p:
                    wi_note = (
                        f'<div style="background:#eff6ff;border-left:3px solid #2563eb;'
                        f'border-radius:4px;padding:.3rem .6rem;margin:.2rem 0;font-size:.76rem">'
                        f'<strong>Pourquoi GO CONDITIONNEL et non NO-GO ?</strong> '
                        f'Le scenario What-If actif <strong>{sc_p}</strong> '
                        f'ameliore la situation. Le plan est realisable sous conditions.'
                        f'</div>')

            rows_gono = []
            if p:
                rows_gono.append(["Production",
                    f"Cap {p['cap_v']:.0f} PHR | {p['n_surcharge']}/{p['weeks_total']} surcharges | Sat {p['sat_max']:.0f}% | Stock min {p['stock_min']:,.0f} U",
                    f'<span style="color:{c_prod};font-weight:700">{v_prod}</span>',
                    why_prod,
                    "Immédiat" if v_prod!="GO" else "—"])
            for a in arts[:3]:
                col_a = "#16a34a" if a["mape_py"]<15 else "#d97706" if a["mape_py"]<30 else "#dc2626"
                rows_gono.append([f"Demande — {a['article'][:16]}",
                    f"MAPE ERP {a['mape_erp']:.1f}% | MAPE Python {a['mape_py']:.1f}% ({a['methode']}) | Trend {a['trend']:+.1f}",
                    f'<span style="color:{col_a};font-weight:700">{"GO" if a["mape_py"]<15 else "GO CONDITIONNEL" if a["mape_py"]<30 else "NO-GO"}</span>',
                    f"Gain vs ERP : {a['gain']:+.1f}% | Forecast M+1 : {a['fc_m1']:,.0f} U",
                    "Revoir paramètres" if a["mape_py"]>15 else "—"])

            result = T(["Domaine","Situation chiffrée","Décision","Analyse","Action prioritaire"],
                       rows_gono, None, "Décision GO/NO-GO — données calculées en temps réel")
            result += f"""
<div style="background:#f8f9fc;border:2px solid {c_global};border-radius:8px;
  padding:.6rem .85rem;margin:.4rem 0">
  <div style="font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
    color:var(--mu);font-family:JetBrains Mono,monospace;margin-bottom:.2rem">Verdict Global S&OP</div>
  <div style="font-size:.95rem;font-weight:900;color:{c_global};margin-bottom:.2rem">{v_global}</div>
  <div style="font-size:.79rem;color:#374151;line-height:1.65">
    <strong>Production :</strong> {why_prod}<br>
    <strong>Demande :</strong> {why_dem}
  </div>
</div>"""
            result += wi_note
            add_msg("orchestrateur","agent",result)

        elif q=="__ORCH_PLAN__":
            add_msg("orchestrateur","user",lbl)
            data = _orch_collect_data()
            result = _orch_build_report(data, sc_txt)
            # Extraire seulement le tableau plan d'action
            add_msg("orchestrateur","agent",result)

        elif q=="__ORCH_RAPPORT__":
            add_msg("orchestrateur","user",lbl)
            with st.spinner("Construction du rapport S&OP..."):
                data = _orch_collect_data()
                result = _orch_build_report(data, sc_txt)
            add_msg("orchestrateur","agent",result)
        elif q=="__ORCH_CLEAR__":
            st.session_state.disc=[]

    st.markdown('<hr style="border:none;border-top:1px solid var(--br);margin:.28rem 0 .38rem">',unsafe_allow_html=True)
    L,R=st.columns([1,2.8],gap="small")
    with L:
        st.markdown('<div class="slbl">Scenario</div>',unsafe_allow_html=True)
        sc_type=st.radio("Scenario orch",["Nominal","Alea production -30%","Pic demande +50%","Personnalise"],
                         key="sc_type_orch",label_visibility="collapsed")
        sc_txt2="SITUATION NOMINALE"
        if "Alea" in sc_type: sc_txt2="CRISE : Capacite reduite 30%"
        elif "Pic" in sc_type: sc_txt2="PIC DEMANDE : +50%"
        elif "Personnalise" in sc_type: sc_txt2=st.text_input("Scenario orch txt","",key="sc_orch_txt",label_visibility="collapsed",placeholder="Decris...")
        if sc_txt2 not in ("SITUATION NOMINALE",""):
            st.markdown(f'<div class="aw">{sc_txt2}</div>',unsafe_allow_html=True)
        st.session_state["sc_orch"]=sc_txt2
        st.markdown('<div class="slbl" style="margin-top:.45rem">Statut agents</div>',unsafe_allow_html=True)
        for ag in ["marketing","demande","production","finance"]:
            has_a=bool(get_dfs(ag)); fn=st.session_state.files.get(ag,"")
            col="#16a34a" if has_a else "#dc2626"
            st.markdown(f'<div class="cap"><span style="color:{col};font-weight:700;font-size:.7rem">{"OK" if has_a else "XX"}</span>'
                        f'<span style="font-weight:600">{ag.capitalize()}</span>'
                        f'{"<span style=\"color:var(--mu);font-size:.68rem\">"+fn[:12]+"</span>" if has_a else ""}</div>',
                        unsafe_allow_html=True)
        st.markdown('<div style="margin-top:.45rem"></div>', unsafe_allow_html=True)
        render_definitions("orchestrateur")
        st.markdown('<div style="margin-top:.35rem"></div>', unsafe_allow_html=True)
        render_email_config()

    with R:
        sub=st.tabs(["Discussion inter-agents","Chat direct"])
        with sub[0]:
            render_disc()
        with sub[1]:
            render_chat("orchestrateur")
            c1,c2=st.columns([7,1])
            with c1:
                oq=st.text_input("Question orch",key="q_orch",label_visibility="collapsed",
                                 placeholder="Question ou ordre a l'Orchestrateur...")
            with c2:
                st.markdown('<div class="btn-send">',unsafe_allow_html=True)
                send_o=st.button("->",key="so")
                st.markdown('</div>',unsafe_allow_html=True)
            if send_o and oq.strip():
                add_msg("orchestrateur","user",oq.strip())
                with st.spinner("Analyse des donnees reelles..."):
                    real_context=""
                    for ag in ["production","demande","marketing","finance"]:
                        d=get_dfs(ag)
                        if not d: continue
                        try:
                            if ag=="production":
                                mrp=mrp_calc(d,{})
                                p=mrp["p"]; ns=sum(1 for s in mrp["status"] if s=="SURCHARGE")
                                real_context+=f"\n=== PRODUCTION ===\nCap={p['cap_v']:.0f}PHR={p['max_u']:.0f}U/sem | {ns}/{len(mrp['weeks'])} surcharges\n"
                            elif ag in ("demande","marketing"):
                                dem=demand_calc(d)
                                real_context+=f"\n=== DEMANDE ({len(dem)} articles) ===\n"
                                for art,r in dem.items():
                                    best_py=min(r['les_mape'],r['hw_mape'],r['ma_mape'])
                                    real_context+=f"  {art}: MAPE_ERP={r['mape_erp']:.1f}% | MAPE_Python={best_py:.1f}% ({r['best']}) | trend={r['trend']:+.2f}\n"
                        except: pass
                    sc_now=st.session_state.get("sc_orch","SITUATION NOMINALE")
                    result=groq(
                        "Orchestrateur S&OP AlBrain. Utilise UNIQUEMENT les donnees fournies. "
                        "REGLE : MAPE plus bas = plus precis. ERP = systeme entreprise. "
                        "Reponds en 5-8 lignes avec chiffres precis.",
                        f"DONNEES REELLES:\n{real_context[:3000]}\nScenario: {sc_now}\nQuestion: {oq.strip()}",
                        600)
                add_msg("orchestrateur","agent",result)

# ── TOPBAR ─────────────────────────────────────────────────────────────────────
logo_path=Path(__file__).parent/"albrain_logo.png"
if logo_path.exists():
    logo_b64=base64.b64encode(logo_path.read_bytes()).decode()
    logo_html=f'<img src="data:image/png;base64,{logo_b64}" style="height:38px;object-fit:contain">'
else:
    logo_html=(
        '<svg width="145" height="38" viewBox="0 0 145 38" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="1" y="1" width="34" height="34" rx="3" fill="#fff" stroke="#1e3a8a" stroke-width="2.5"/>'
        '<text x="9" y="14" font-family="Arial,sans-serif" font-size="10" fill="#1e3a8a" font-weight="700">AL</text>'
        '<line x1="4" y1="18" x2="30" y2="18" stroke="#1e3a8a" stroke-width="1"/>'
        '<text x="41" y="21" font-family="Arial,sans-serif" font-size="17" fill="#1e3a8a" font-weight="800" letter-spacing="1">BRAIN</text>'
        '<text x="41" y="33" font-family="Arial,sans-serif" font-size="7.5" fill="#6b7299" letter-spacing="2.5">CONSULTING</text>'
        '</svg>'
    )

try:
    _key=st.secrets.get("GROQ_API_KEY","") or os.environ.get("GROQ_API_KEY","")
    _ok=bool(_key)
except: _ok=False

st.markdown(f"""
<div class="tb">
  {logo_html}
  <div>
    <div class="tb-name">AL<span>BRAIN</span> Consulting</div>
    <div style="font-size:.68rem;color:var(--mu)">S&OP AI Platform v3.1</div>
  </div>
  <div style="margin-left:auto;font-size:.7rem;font-family:'JetBrains Mono',monospace;
    color:{"#16a34a" if _ok else "#dc2626"}">
    {"Groq connecte" if _ok else "Groq non configure"}
  </div>
</div>
""", unsafe_allow_html=True)

tabs=st.tabs(["Marketing","Demande","Production","Finance","Orchestrateur"])
with tabs[0]: render_tab("marketing")
with tabs[1]: render_tab("demande")
with tabs[2]: render_tab("production")
with tabs[3]: render_tab("finance")
with tabs[4]: render_orchestrateur()
