
import re
import json
import time
import math
import base64
import textwrap
import pandas as pd
import requests
from bs4 import BeautifulSoup

# -----------------------------
# Fetch & parse
# -----------------------------
def fetch_html(url: str, timeout: int = 20) -> tuple[str, BeautifulSoup]:
    """Download HTML and return (html, soup)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CRO-LP-Agent/1.0; +https://example.com)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "lxml")
    return html, soup

# -----------------------------
# Utility
# -----------------------------
def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def word_count(s: str) -> int:
    return len(re.findall(r"[A-Za-zÀ-ÿ0-9]+", s or ""))

def has_cta_like(a_tag) -> bool:
    if not a_tag: return False
    text = (a_tag.get_text() or "").lower().strip()
    cls  = " ".join(a_tag.get("class", [])).lower()
    role = (a_tag.get("role") or "").lower()
    href = (a_tag.get("href") or "").lower()
    btn_words = ["start", "gratis", "free", "try", "proef", "demo", "offerte", "aanvraag", "koop", "bestel", "aanmelden", "download", "inschrijven", "contact"]
    score = 0
    if role == "button" or "button" in cls or "btn" in cls: score += 1
    if any(w in text for w in btn_words): score += 1
    if href.startswith("#contact") or href.startswith("mailto:"): score += 1
    return score >= 1

# -----------------------------
# Basic automated checks
# -----------------------------
def check_title_length(soup: BeautifulSoup) -> dict:
    t = norm_text(soup.title.get_text() if soup.title else "")
    l = len(t)
    ok = 10 <= l <= 65
    sev = "WARN" if not ok else "PASS"
    return {"name":"Title length 10–65", "result": sev, "evidence": f"{l} chars: {t[:120]}"}

def check_meta_description(soup: BeautifulSoup) -> dict:
    tag = soup.find("meta", attrs={"name":"description"})
    d = norm_text(tag["content"]) if tag and tag.get("content") else ""
    l = len(d)
    if not d:
        return {"name":"Meta description present", "result":"FAIL", "evidence":"Not found"}
    ok = 50 <= l <= 160
    sev = "WARN" if not ok else "PASS"
    return {"name":"Meta description 50–160", "result": sev, "evidence": f"{l} chars: {d[:160]}"}

def check_h1_presence(soup: BeautifulSoup) -> dict:
    h1s = [norm_text(h.get_text()) for h in soup.find_all("h1")]
    if not h1s:
        return {"name":"H1 present", "result":"FAIL", "evidence":"No H1 found"}
    return {"name":"H1 present", "result":"PASS", "evidence": f"H1(s): {h1s[:3]}"}

def check_viewport(soup: BeautifulSoup) -> dict:
    vp = soup.find("meta", attrs={"name":"viewport"})
    if not vp:
        return {"name":"Viewport meta", "result":"FAIL", "evidence":"Missing meta viewport"}
    content = (vp.get("content") or "").lower()
    ok = "width=device-width" in content
    return {"name":"Mobile responsiveness meta", "result": "PASS" if ok else "WARN", "evidence": content}

def check_favicon(soup: BeautifulSoup) -> dict:
    ico = soup.find("link", rel=lambda x: x and "icon" in x.lower())
    if not ico:
        return {"name":"Favicon link", "result":"WARN", "evidence":"No <link rel='icon'> found"}
    return {"name":"Favicon link", "result":"PASS", "evidence": str(ico)[:140]}

def check_canonical(soup: BeautifulSoup) -> dict:
    can = soup.find("link", rel=lambda x: x and "canonical" in x.lower())
    if not can:
        return {"name":"Canonical link", "result":"WARN", "evidence":"Missing <link rel='canonical'> (optional)"}
    return {"name":"Canonical link", "result":"PASS", "evidence": can.get("href","")}

def check_image_alts(soup: BeautifulSoup) -> dict:
    imgs = soup.find_all("img")
    if not imgs:
        return {"name":"Image alts coverage", "result":"PASS", "evidence":"No <img> tags"}
    total = len(imgs)
    with_alt = sum(1 for i in imgs if (i.get("alt") or "").strip())
    pct = (with_alt / total) * 100
    res = "PASS" if pct >= 80 else ("WARN" if pct >= 50 else "FAIL")
    return {"name":"Image alts coverage", "result":res, "evidence": f"{with_alt}/{total} ({pct:.0f}%) have alt"}

def check_cta_above_fold(soup: BeautifulSoup) -> dict:
    # Approx: CTA link in first ~1500 chars of body text
    body = soup.body or soup
    html = str(body)
    snippet = html[:2000]
    soup_early = BeautifulSoup(snippet, "lxml")
    links = soup_early.find_all("a")
    found = any(has_cta_like(a) for a in links)
    return {"name":"CTA above the fold (approx.)", "result":"PASS" if found else "WARN", "evidence": "Found early CTA" if found else "Not detected early"}

def check_forms_labels(soup: BeautifulSoup) -> dict:
    forms = soup.find_all("form")
    inputs = soup.find_all(["input","textarea","select"])
    labels = soup.find_all("label")
    if forms and inputs:
        ok_labels = len(labels) >= max(1, len(inputs)//3)
        return {"name":"Forms & labels present", "result": "PASS" if ok_labels else "WARN", "evidence": f"forms={len(forms)}, inputs={len(inputs)}, labels={len(labels)}"}
    return {"name":"Forms & labels present", "result":"WARN", "evidence": "No forms/inputs detected"}

def check_analytics_trust(soup: BeautifulSoup) -> dict:
    scripts = " ".join(s.get("src","") + " " + (s.get_text() or "") for s in soup.find_all("script"))
    hit = any(w in scripts.lower() for w in ["gtag(", "googletagmanager.com", "fbq(", "clarity(", "hotjar", "dataLayer"])
    return {"name":"Analytics/trust snippet", "result":"PASS" if hit else "WARN", "evidence":"Detected common tracker" if hit else "No tracker detected"}

def check_url_readability(url: str) -> dict:
    # Score URL: fewer query params, readable words, limited length
    path = re.sub(r"https?://", "", url).split("/",1)[-1]
    path_len = len(path)
    qs = "?" in url
    words = re.findall(r"[a-z0-9\-]+", path.lower())
    wordy = sum(1 for w in words if len(w) >= 3)
    score = 0
    if path_len <= 80: score += 1
    if not qs: score += 1
    if wordy >= 2: score += 1
    res = "PASS" if score >= 2 else "WARN"
    return {"name":"Logical, readable URL", "result": res, "evidence": f"path_len={path_len}, query={'yes' if qs else 'no'}, words≥3={wordy}"}

# -----------------------------
# Checklist loader (from Excel)
# -----------------------------
def load_checklist_from_excel(path_or_buf) -> pd.DataFrame:
    """
    Expect columns: 'Tip' (name), optional 'Categorie','Uitleg','Prioriteit','Moeilijkheidsgraad'.
    Everything becomes a row; by default we mark check_type='auto' if we know how to check it,
    otherwise 'manual'.
    """
    df = pd.read_excel(path_or_buf, sheet_name=0)
    # Normalize columns
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)
    for col in ["Categorie","Tip","Prioriteit","Moeilijkheidsgraad","Uitleg"]:
        if col not in df.columns:
            df[col] = ""
    df["Tip_norm"] = df["Tip"].astype(str).str.strip().str.lower()

    # Map tips to built-in automated checks
    tip_to_check = {
        "logische url": "url_readable",
        "mobiele responsiviteit": "viewport",
        "favicon": "favicon",
        "inhoud boven de vouw": "cta_above_fold",
        "laadsnelheid van pagina": "speed_manual",
        "compatibiliteit tussen browsers": "manual",
        "sticky cta": "sticky_manual",
        "leadmeldingswaarschuwingen": "manual",
        "duidelijke berichten in de hero-sectie": "manual",
        "productiekwaliteit en professionaliteit": "manual",
    }

    df["check_type"] = df["Tip_norm"].map(tip_to_check).fillna("manual")
    return df

# -----------------------------
# Run full analysis
# -----------------------------
def analyze(url: str, checklist_df: pd.DataFrame) -> dict:
    html, soup = fetch_html(url)

    automated = [
        check_title_length(soup),
        check_meta_description(soup),
        check_h1_presence(soup),
        check_viewport(soup),
        check_favicon(soup),
        check_canonical(soup),
        check_image_alts(soup),
        check_cta_above_fold(soup),
        check_forms_labels(soup),
        check_analytics_trust(soup),
        check_url_readability(url),
    ]

    auto_index = {a["name"].lower(): a for a in automated}

    # Merge with checklist: attach results where possible, else mark MANUAL
    rows = []
    for _, r in checklist_df.iterrows():
        tip = str(r["Tip"] or "").strip()
        tip_norm = tip.lower()
        cat = str(r["Categorie"] or "").strip()
        prio = str(r["Prioriteit"] or "").strip()
        diff = str(r["Moeilijkheidsgraad"] or "").strip()
        uitleg = str(r["Uitleg"] or "").strip()
        ctype = r.get("check_type","manual")

        result = "N/A"
        evidence = ""
        mapped = None

        # heuristic mapping from Dutch tip -> auto check names
        mapping = {
            "logische url": "logical, readable url",
            "mobiele responsiviteit": "mobile responsiveness meta",
            "favicon": "favicon link",
            "inhoud boven de vouw": "cta above the fold (approx.)",
        }
        if ctype != "manual":
            target = mapping.get(tip_norm)
            if target and target in auto_index:
                payload = auto_index[target]
                result = payload["result"]
                evidence = payload["evidence"]
                mapped = payload["name"]
            elif ctype.endswith("_manual"):
                result = "REVIEW"
                evidence = "Handmatige check aanbevolen (niet volledig te automatiseren)."

        if ctype == "manual":
            result = "REVIEW"
            evidence = "Handmatige beoordeling nodig (inhoud/UX/techniek)."

        rows.append({
            "Categorie": cat,
            "Tip": tip,
            "Prioriteit": prio,
            "Moeilijkheidsgraad": diff,
            "Uitleg": uitleg,
            "Check type": ctype,
            "Result": result,
            "Evidence": evidence,
            "Auto check": mapped or "",
        })

    # Also include any automated checks not present in checklist
    known_tips = set(str(x).strip().lower() for x in checklist_df["Tip"])
    for a in automated:
        if a["name"].lower() not in known_tips:
            rows.append({
                "Categorie": "Automated (extra)",
                "Tip": a["name"],
                "Prioriteit": "",
                "Moeilijkheidsgraad": "",
                "Uitleg": "",
                "Check type": "auto",
                "Result": a["result"],
                "Evidence": a["evidence"],
                "Auto check": a["name"],
            })

    out_df = pd.DataFrame(rows)

    # Simple scoring: PASS=1, WARN=0.5, FAIL=0, REVIEW=0.5, N/A ignored
    score_map = {"PASS":1.0, "WARN":0.5, "FAIL":0.0, "REVIEW":0.5}
    valid = out_df[out_df["Result"].isin(score_map.keys())]
    score = valid["Result"].map(score_map).mean() if not valid.empty else None

    summary = {
        "url": url,
        "score_0_1": None if score is None else round(float(score), 3),
        "counts": dict(out_df["Result"].value_counts()),
    }
    return {"summary": summary, "checks": out_df}

# -----------------------------
# HTML/Markdown rendering
# -----------------------------
def to_markdown(result: dict) -> str:
    s = result["summary"]
    md = []
    md.append(f"# CRO Landing Page Report\n")
    md.append(f"- URL: {s['url']}")
    md.append(f"- Score (0–1): {s['score_0_1']}")
    md.append(f"- Counts: {json.dumps(s['counts'], ensure_ascii=False)}\n")
    md.append("## Checks\n")
    df = result["checks"][["Categorie","Tip","Result","Evidence","Check type","Prioriteit","Moeilijkheidsgraad","Uitleg"]]
    for _, r in df.iterrows():
        md.append(f"### {r['Tip']}  \n*Categorie:* {r['Categorie']}  \n*Result:* **{r['Result']}**  \n*Evidence:* {r['Evidence']}  \n*Type:* {r['Check type']}  \n*Prioriteit:* {r['Prioriteit']}  \n*Moeilijkheid:* {r['Moeilijkheidsgraad']}  \n{r['Uitleg'] or ''}\n")
    return "\n".join(md)

def to_html(result: dict) -> str:
    md = to_markdown(result)
    try:
        # very simple md->html
        html = md
        html = re.sub(r"^# (.*)$", r"<h1>\1</h1>", html, flags=re.M)
        html = re.sub(r"^## (.*)$", r"<h2>\1</h2>", html, flags=re.M)
        html = re.sub(r"^### (.*)$", r"<h3>\1</h3>", html, flags=re.M)
        html = html.replace("**","<b>").replace("  \n","<br/>")
        html = "<html><body style='font-family:Arial, sans-serif; padding:16px;'>" + html + "</body></html>"
        return html
    except Exception:
        return "<html><body><pre>"+md+"</pre></body></html>"
