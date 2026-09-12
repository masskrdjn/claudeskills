"""Suite de tests du routage selectif multi-modeles.

Run with Python stdlib + Windows PowerShell 5.1.
Niveaux 1 et 2 uniquement : aucun appel de modele, aucun cout.
Le niveau 3 (comportement reel de Claude Code) est dans smoketest_live.py.

    python smoketest.py [racine_du_depot]
"""

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       else os.path.dirname(os.path.abspath(__file__)))

ROLES = ("architect", "builder", "researcher", "runner", "scout")
DOCS = ("CLAUDE.md", ".claude/skills/quota-orchestrator/SKILL.md",
        "README.md", "README.fr.md")

MODEL_ALIASES = {"opus", "sonnet", "haiku", "fable", "inherit", "opusplan"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}

# Modeles sans support de `effort`. Ecrire le champ pour eux est une erreur.
NO_EFFORT_MODELS = {"haiku"}

failures = []


def check(name, fn):
    try:
        detail = fn()
        print("  ok    %s%s" % (name, (" - " + detail) if detail else ""))
    except AssertionError as exc:
        failures.append((name, str(exc)))
        print("  ECHEC %s\n          %s" % (name, exc))
    except Exception as exc:  # noqa: BLE001 - un test cassé est un échec
        failures.append((name, "%s: %s" % (type(exc).__name__, exc)))
        print("  ERREUR %s\n          %s: %s" % (name, type(exc).__name__, exc))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text, path):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "frontmatter absent dans %s" % path
    fields = dict(re.findall(r"^([a-zA-Z]+):\s*(.+?)\s*$", m.group(1), re.M))
    return fields, text[m.end():]


def role_files():
    out = {}
    for role in ROLES:
        rel = ".claude/agents/%s.md" % role
        fm, body = frontmatter(read(rel), rel)
        out[role] = (fm, body)
    return out


# --- Niveau 1 : structure et configuration ---------------------------------

def t_inventaire():
    expected = ["CLAUDE.md", "README.md", "README.fr.md",
                ".claude/settings.json", "extract_claude_jsonl.ps1",
                "test_extract_claude_jsonl.py",
                "smoketest.py", "smoketest_live.py",
                ".claude/skills/quota-orchestrator/SKILL.md"]
    expected += [".claude/agents/%s.md" % r for r in ROLES]
    missing = [p for p in expected if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing, "fichiers manquants : %s" % missing
    return "%d fichiers attendus presents" % len(expected)


def t_aucun_residu_codex():
    """Le depot doit etre purement Claude Code."""
    banned_paths = [".codex", ".agents", "AGENTS.md"]
    present = [p for p in banned_paths if os.path.exists(os.path.join(ROOT, p))]
    assert not present, "residus Codex sur disque : %s" % present

    pattern = re.compile(r"gpt-[0-9]|model_reasoning_effort|developer_instructions"
                         r"|sandbox_mode|--yolo|dangerously-bypass-approvals")
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            if fn in ("smoketest.py", "smoketest_live.py"):
                continue
            if not fn.endswith((".md", ".json", ".ps1", ".py")):
                continue
            full = os.path.join(dirpath, fn)
            with open(full, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    if pattern.search(line):
                        hits.append("%s:%d" % (os.path.relpath(full, ROOT), i))
    assert not hits, "vocabulaire Codex residuel : %s" % hits
    return "aucun residu"


def t_roles_frontmatter():
    for role, (fm, body) in role_files().items():
        for key in ("name", "description", "model", "tools"):
            assert key in fm, "%s : champ '%s' manquant" % (role, key)
        assert fm["name"] == role, \
            "%s : name='%s' ne correspond pas au nom de fichier" % (role, fm["name"])
        assert len(fm["description"]) > 40, "%s : description trop courte" % role
        assert len(body.strip()) > 200, "%s : corps d'instructions trop court" % role
    return "5 roles"


def t_modeles_valides():
    seen = []
    for role, (fm, _) in role_files().items():
        model = fm["model"]
        assert model in MODEL_ALIASES or model.startswith("claude-"), \
            "%s : modele '%s' non reconnu" % (role, model)
        seen.append("%s=%s" % (role, model))
    return ", ".join(sorted(seen))


def t_efforts_valides():
    for role, (fm, _) in role_files().items():
        model, effort = fm["model"], fm.get("effort")
        if model in NO_EFFORT_MODELS:
            assert effort is None, \
                ("%s : '%s' ne supporte pas effort, le champ ne doit pas etre ecrit "
                 "(trouve '%s')" % (role, model, effort))
        else:
            assert effort in EFFORTS, \
                "%s : effort '%s' invalide" % (role, effort)
    return "runner sans effort, 4 roles avec effort valide"


def t_aucun_role_ne_delegue():
    """Invariant : la racine garde la responsabilite du routage."""
    for role, (fm, body) in role_files().items():
        tools = fm["tools"]
        assert "Agent" not in tools, \
            "%s : 'Agent' present dans tools, le role peut re-deleguer" % role
        assert "Task" not in tools, "%s : 'Task' present dans tools" % role
        assert "ne delegue pas" in body.replace("é", "e").replace("è", "e"), \
            "%s : le corps ne rappelle pas l'interdiction de deleguer" % role
    return "5 roles sans outil de delegation"


def t_frontieres_outils():
    expect = {
        "scout":      {"deny": ["Write", "Edit", "Bash", "WebSearch", "WebFetch"]},
        "researcher": {"deny": ["Write", "Edit", "Bash"]},
        "architect":  {"deny": ["Write", "Edit", "Bash", "WebSearch", "WebFetch"]},
        "runner":     {"allow": ["Bash"]},
        "builder":    {"allow": ["Edit", "Write"]},
    }
    files = role_files()
    for role, rules in expect.items():
        tools = files[role][0]["tools"]
        for banned in rules.get("deny", []):
            assert banned not in tools, \
                "%s : outil '%s' ne devrait pas etre accorde (tools: %s)" % (role, banned, tools)
        for needed in rules.get("allow", []):
            assert needed in tools, \
                "%s : outil '%s' requis pour sa mission (tools: %s)" % (role, needed, tools)
    return "lecture seule tenue pour scout/researcher/architect"


def t_aucun_fable_en_dur():
    """Coeur de la conception : Fable n'est jamais ecrit dans un role."""
    for role, (fm, body) in role_files().items():
        assert "fable" not in fm["model"].lower(), \
            "%s : modele Fable ecrit en dur, il ne doit venir que d'une escalade" % role
    settings = read(".claude/settings.json")
    assert "fable" not in settings.lower(), \
        "settings.json reference Fable ; l'escalade doit rester dynamique"
    return "aucun fable sur disque"


def t_skill_frontmatter():
    rel = ".claude/skills/quota-orchestrator/SKILL.md"
    fm, body = frontmatter(read(rel), rel)
    assert fm.get("name") == "quota-orchestrator", \
        "name='%s' ne correspond pas au dossier" % fm.get("name")
    assert len(fm.get("description", "")) > 80, "description trop courte"
    for needed in ("Complete", "resolvedModel", "Accès Fable"):
        assert needed in body, "le skill ne couvre pas '%s'" % needed
    return "name, description et sections cles presentes"


def t_procedure_fable_deterministe():
    """La detection du plan doit rester mecanique, pas une question ouverte."""
    body = read(".claude/skills/quota-orchestrator/SKILL.md")
    for needed in ("claude auth status", "subscriptionType", "apiProvider",
                   "2.1.257", "availableModels"):
        assert needed in body, \
            "la procedure d'acces Fable ne s'appuie pas sur '%s'" % needed
    # Disponible ne vaut pas autorise : le consentement reste explicite.
    assert "usage credits" in body, \
        "le surcout en usage credits n'est pas mentionne"
    assert "-p" in body and "sans" in body, \
        "le risque du mode non interactif (facturation sans consentement) est absent"
    return "table de decision mecanique + consentement explicite"


def t_settings_json():
    raw = read(".claude/settings.json")
    cfg = json.loads(raw)  # leve si JSON invalide
    assert "model" not in cfg, \
        "settings.json pinne 'model' : cela ecraserait le defaut adapte au plan"
    assert "maxEffortLevel" not in cfg, \
        "'maxEffortLevel' plafonnerait les escalades vers max"
    assert cfg.get("effortLevel") in EFFORTS, \
        "effortLevel '%s' invalide" % cfg.get("effortLevel")
    for model, sub in cfg.get("modelSettings", {}).items():
        assert model.startswith("claude-"), \
            "modelSettings : cle '%s' devrait etre un identifiant complet" % model
        assert sub.get("effortLevel") in EFFORTS, \
            "modelSettings/%s : effortLevel invalide" % model
    return "cles valides, aucun pinning de modele"


def t_coherence_documentaire():
    """Le depot d'origine avait un README desynchronise de sa config."""
    files = role_files()
    bad = []
    for role, (fm, _) in files.items():
        model, effort = fm["model"], fm.get("effort")
        for doc in DOCS:
            rows = [l.strip() for l in read(doc).splitlines()
                    if l.startswith("| `%s`" % role)]
            if not rows:
                bad.append("%s : role %s absent" % (doc, role)); continue
            row = rows[0]
            if "`%s`" % model not in row:
                bad.append("%s / %s : modele attendu `%s` -> %s" % (doc, role, model, row))
            if effort and "`%s`" % effort not in row:
                bad.append("%s / %s : effort attendu `%s` -> %s" % (doc, role, effort, row))
    assert not bad, "desynchronisation :\n          " + "\n          ".join(bad)
    return "5 roles x 4 documents alignes"


def t_tarifs_coherents():
    """La table de prix du script doit correspondre aux README."""
    ps = read("extract_claude_jsonl.ps1")
    table = {}
    for m in re.finditer(
            r"'(claude-[\w.-]+)'\s*=\s*@\{\s*Input\s*=\s*([\d.]+);\s*"
            r"Output\s*=\s*([\d.]+);\s*CacheWrite5m\s*=\s*([\d.]+);\s*"
            r"CacheWrite1h\s*=\s*([\d.]+);\s*CacheRead\s*=\s*([\d.]+)", ps):
        table[m.group(1)] = tuple(float(g) for g in m.groups()[1:])
    assert table, "table de prix introuvable dans le script"
    expected = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0),
                "claude-haiku-4-5": (1.0, 5.0), "claude-fable-5-1": (10.0, 50.0)}
    for model, price in expected.items():
        got = table.get(model)
        assert got and got[:2] == price, \
            "%s : script dit %s, attendu %s" % (model, got, price)

    # Invariant de tarification du cache, verifie contre une facturation reelle :
    # ecriture 5 min = 1,25x l'entree, ecriture 1 h = 2x l'entree.
    for model, (inp, _out, cw5m, cw1h, _cr) in table.items():
        assert abs(cw5m - inp * 1.25) < 1e-9, \
            "%s : cache 5 min a %.2f, attendu %.2f (1,25x %.2f)" % (model, cw5m, inp * 1.25, inp)
        assert abs(cw1h - inp * 2.0) < 1e-9, \
            "%s : cache 1 h a %.2f, attendu %.2f (2x %.2f)" % (model, cw1h, inp * 2.0, inp)

    # Les memes chiffres doivent apparaitre dans les deux README.
    for doc in ("README.md", "README.fr.md"):
        txt = read(doc)
        for role, cell in (("`runner`", "| 1 | 5 |"), ("`scout`", "| 2 | 10 |")):
            rows = [l for l in txt.splitlines() if l.startswith("| " + role)]
            assert rows and cell in rows[0], \
                "%s : tarifs de %s absents ou differents -> %s" % (doc, role, rows)
    return "%d modeles tarifes, README alignes" % len(table)


def t_readme_bilingue():
    en, fr = read("README.md"), read("README.fr.md")
    assert "[Français](README.fr.md)" in en, "README.md ne pointe pas vers le FR"
    assert "[English](README.md)" in fr, "README.fr.md ne pointe pas vers l'EN"
    # Meme nombre de lignes de tableau de routage dans les deux langues.
    def rows(t):
        return len([l for l in t.splitlines() if re.match(r"^\| `?(Primary|Principal|scout|researcher|runner|builder|architect)", l)])
    assert rows(en) == rows(fr) == 6, \
        "tables de routage desequilibrees : EN=%d FR=%d" % (rows(en), rows(fr))
    return "liens croises et tables alignes"


def t_claude_md_interdits():
    body = read("CLAUDE.md")
    for needed in ("--dangerously-skip-permissions", "bypassPermissions",
                   "resolvedModel", "Complete = false"):
        assert needed in body, "CLAUDE.md ne mentionne pas '%s'" % needed
    return "regles de securite et de preuve presentes"


# --- Niveau 2 : instrument de mesure ---------------------------------------

def t_harness_interne():
    proc = subprocess.run([sys.executable, "test_extract_claude_jsonl.py"],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, \
        "harness en echec :\n%s\n%s" % (proc.stdout[-2000:], proc.stderr[-2000:])
    n = re.search(r"(\d+) tests passes", proc.stdout)
    assert n, "sortie du harness inattendue : %s" % proc.stdout[-500:]
    return "%s tests internes" % n.group(1)


def t_dossier_vide_echoue_proprement():
    """Un dossier sans transcript ne doit pas produire un rapport vide et 'complet'."""
    tmp = tempfile.mkdtemp(prefix="smoke_empty_")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "extract_claude_jsonl.ps1"),
         "-SessionsDir", tmp, "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode != 0, \
        "le script a reussi sur un dossier vide, il aurait du echouer"
    assert "Aucun transcript" in (proc.stdout + proc.stderr), \
        "message d'erreur peu clair : %s" % (proc.stdout + proc.stderr)[-300:]
    return "erreur explicite, pas de faux rapport"


def t_dossier_inexistant_echoue():
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "extract_claude_jsonl.ps1"),
         "-SessionsDir", os.path.join(ROOT, "_nexiste_pas_"), "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode != 0, "le script aurait du echouer"
    return "erreur explicite"


def t_arithmetique_du_cout():
    """Verification independante du calcul, sans reutiliser la formule du script."""
    tmp = tempfile.mkdtemp(prefix="smoke_cost_")
    rec = {"type": "assistant", "timestamp": "2026-09-12T08:00:00.000Z",
           "effort": "medium",
           "message": {"id": "m1", "model": "claude-sonnet-5", "role": "assistant",
                       "usage": {"input_tokens": 1_000_000,
                                 "output_tokens": 1_000_000,
                                 "cache_creation_input_tokens": 2_000_000,
                                 "cache_creation": {
                                     "ephemeral_5m_input_tokens": 1_000_000,
                                     "ephemeral_1h_input_tokens": 1_000_000},
                                 "cache_read_input_tokens": 1_000_000}}}
    with open(os.path.join(tmp, "s.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    export = os.path.join(tmp, "r.json")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "extract_claude_jsonl.ps1"),
         "-SessionsDir", tmp, "-ExportPath", export, "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-800:]
    with open(export, encoding="utf-8-sig") as fh:
        report = json.load(fh)
    assert report["Complete"] is True, report["Diagnostics"]
    # Un million de tokens de chaque sorte : le cout est la somme des tarifs.
    # Les deux ecritures de cache se tarifent differemment selon leur TTL.
    attendu = 2.0 + 10.0 + 2.50 + 4.00 + 0.20
    b = report["Buckets"][0]
    assert b["CacheWrite5mTokens"] == 1_000_000 and b["CacheWrite1hTokens"] == 1_000_000, \
        "ventilation du cache perdue : %s" % b
    got = b["CostUsd"]
    assert abs(got - attendu) < 1e-9, \
        "cout %.4f, attendu %.4f (2 + 10 + 2.50 + 4.00 + 0.20)" % (got, attendu)
    return "1M de chaque sorte, deux TTL de cache = %.2f USD" % attendu


# --- Niveau 2 bis : environnement ------------------------------------------

def t_version_claude_code():
    proc = subprocess.run(["powershell", "-NoProfile", "-Command",
                           "claude --version"], capture_output=True, text=True)
    assert proc.returncode == 0, "claude introuvable : %s" % proc.stderr[-200:]
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", proc.stdout)
    assert m, "version illisible : %s" % proc.stdout
    version = tuple(int(x) for x in m.groups())
    # Le support de Fable 5.1 demande 2.1.257 ou plus recent.
    if version < (2, 1, 257):
        return ("v%d.%d.%d - sous le prerequis Fable 5.1 (2.1.257) : "
                "l'escalade architect->fable ne peut pas aboutir ici" % version)
    return "v%d.%d.%d - Fable 5.1 supporte" % version


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Ce harness requiert Windows PowerShell 5.1.")
        sys.exit(1)

    print("Depot teste : %s\n" % ROOT)
    groups = [
        ("Niveau 1 - structure et configuration", [
            t_inventaire, t_aucun_residu_codex, t_roles_frontmatter,
            t_modeles_valides, t_efforts_valides, t_aucun_role_ne_delegue,
            t_frontieres_outils, t_aucun_fable_en_dur, t_skill_frontmatter,
            t_procedure_fable_deterministe,
            t_settings_json, t_coherence_documentaire, t_tarifs_coherents,
            t_readme_bilingue, t_claude_md_interdits]),
        ("Niveau 2 - instrument de mesure", [
            t_harness_interne, t_dossier_vide_echoue_proprement,
            t_dossier_inexistant_echoue, t_arithmetique_du_cout]),
        ("Environnement", [t_version_claude_code]),
    ]
    total = 0
    for title, tests in groups:
        print(title)
        for test in tests:
            check(test.__name__[2:].replace("_", " "), test)
            total += 1
        print("")

    if failures:
        print("%d ECHEC(S) sur %d tests" % (len(failures), total))
        sys.exit(1)
    print("%d tests passes." % total)
