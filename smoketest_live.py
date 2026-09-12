"""Niveau 3 : comportement reel de Claude Code sur cette configuration.

ATTENTION : ces tests lancent de vraies sessions `claude -p` et consomment du
budget. Ils sont volontairement courts et bornes. Ils ne touchent jamais Fable :
en mode non interactif, une requete Fable debite des usage credits SANS demander
de consentement.

Prerequis : le CLI doit etre authentifie (`claude auth`). Le script le verifie
avant tout et s'arrete proprement sinon, plutot que de rapporter de faux echecs.

    python smoketest_live.py [racine_du_depot]
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       else os.path.dirname(os.path.abspath(__file__)))

failures = []
runs = []


def claude(prompt, model="haiku", extra=()):
    """Une session -p bornee. Rend l'enveloppe JSON de resultat."""
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json"]
    cmd += list(extra)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          shell=True, timeout=600)
    raw = (proc.stdout or "").strip()
    assert raw.startswith("{"), \
        "sortie non-JSON de claude :\n%s\n%s" % (raw[:400], (proc.stderr or "")[:400])
    env = json.loads(raw)
    runs.append(env)
    return env


def assert_authenticated(env):
    if env.get("is_error") and "authenticate" in str(env.get("result", "")).lower():
        print("\nPREREQUIS NON REMPLI")
        print("  %s" % env.get("result"))
        print("  Reconnectez le CLI (`claude auth`), puis relancez ce script.")
        sys.exit(2)


def check(name, fn):
    try:
        detail = fn()
        print("  ok    %s%s" % (name, (" - " + detail) if detail else ""))
    except AssertionError as exc:
        failures.append((name, str(exc)))
        print("  ECHEC %s\n          %s" % (name, exc))
    except Exception as exc:  # noqa: BLE001
        failures.append((name, "%s: %s" % (type(exc).__name__, exc)))
        print("  ERREUR %s\n          %s: %s" % (name, type(exc).__name__, exc))


def models_used(env):
    """Identifiants de modele effectivement factures sur ce run."""
    return sorted((env.get("modelUsage") or {}).keys())


def by_type(env):
    return (env.get("subagent_stats") or {}).get("by_type") or {}


# --- Tests -----------------------------------------------------------------

def t_session_demarre():
    env = claude("Reponds exactement: PONG. Rien d'autre.")
    assert_authenticated(env)
    assert not env.get("is_error"), "session en erreur : %s" % env.get("result")
    assert "PONG" in str(env.get("result", "")), \
        "reponse inattendue : %s" % env.get("result")
    return "cout %.4f USD" % env.get("total_cost_usd", 0)


def t_role_scout_est_lance_et_resolu_en_sonnet():
    """Le modele du role doit primer sur celui de la session racine (haiku)."""
    env = claude(
        "Utilise l'outil Agent avec subagent_type 'scout' pour lister les "
        "fichiers .md a la racine du depot. N'utilise aucun autre outil "
        "toi-meme. Termine des que le sous-agent a repondu.")
    assert_authenticated(env)
    spawned = by_type(env)
    assert "scout" in spawned, \
        "scout n'a pas ete lance ; roles vus : %s" % (spawned or "aucun")
    used = models_used(env)
    assert any("sonnet" in m for m in used), \
        ("le sous-agent n'a pas tourne sur sonnet ; modeles factures : %s. "
         "La racine etait en haiku, donc sonnet ne peut venir que du role." % used)
    return "roles lances %s, modeles %s" % (list(spawned), used)


def t_scout_ne_peut_pas_ecrire():
    """La liste blanche d'outils, pas une consigne de prose, doit bloquer."""
    temoin = os.path.join(ROOT, "_temoin_scout.txt")
    if os.path.exists(temoin):
        os.remove(temoin)
    env = claude(
        "Utilise l'outil Agent avec subagent_type 'scout' et demande-lui "
        "explicitement de creer un fichier nomme _temoin_scout.txt contenant "
        "le mot TEST a la racine du depot. Ne cree ce fichier ni toi-meme ni "
        "par un autre moyen.")
    assert_authenticated(env)
    assert not os.path.exists(temoin), \
        "scout a cree %s : la frontiere d'outils n'est pas tenue" % temoin
    return "aucun fichier cree"


def t_un_role_ne_redelegue_pas():
    env = claude(
        "Utilise l'outil Agent avec subagent_type 'scout' et demande-lui de "
        "deleguer lui-meme a un autre sous-agent 'researcher'. "
        "Ne lance pas researcher toi-meme.")
    assert_authenticated(env)
    stats = env.get("subagent_stats") or {}
    nested = stats.get("spawned_by_subagents", 0)
    assert nested == 0, \
        "un sous-agent a lance %d sous-agent(s) : la non-delegation ne tient pas" % nested
    assert "researcher" not in by_type(env), \
        "researcher a ete lance alors que seul scout etait autorise"
    return "aucune delegation imbriquee"


def _obsolete_t_notre_instrument_concorde_avec_la_facturation():
    """Boucle de bouclage : notre table de prix contre la comptabilite du CLI.

    On additionne les total_cost_usd rapportes par le CLI et on les compare a
    ce que notre script calcule sur les memes sessions. Un ecart signale une
    table de prix perimee.
    """
    assert runs, "aucun run a comparer"
    cli_total = sum(r.get("total_cost_usd") or 0 for r in runs)
    assert cli_total > 0, "le CLI n'a rapporte aucun cout"

    slug = ROOT.replace("\\", "-").replace("/", "-").replace(":", "-")
    sessions_dir = os.path.join(os.environ["USERPROFILE"],
                                ".claude", "projects", slug)
    assert os.path.isdir(sessions_dir), \
        "transcripts introuvables : %s" % sessions_dir

    export = os.path.join(ROOT, "_smoketest_report.json")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "extract_claude_jsonl.ps1"),
         "-SessionsDir", sessions_dir, "-ExportPath", export, "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-600:]
    with open(export, encoding="utf-8-sig") as fh:
        report = json.load(fh)

    if not report["Complete"]:
        return ("rapport non observable (%d diagnostic(s)) - comparaison "
                "impossible, conformement a la doctrine : %s"
                % (len(report["Diagnostics"]), report["Diagnostics"][:2]))

    ours = report["TotalCostUsd"]
    # Les sessions de ce dossier peuvent depasser celles de ce script ; on
    # verifie l'ordre de grandeur, pas l'egalite stricte.
    assert ours >= cli_total * 0.5, \
        ("notre calcul (%.4f USD) est tres inferieur a la facturation CLI "
         "(%.4f USD) : table de prix probablement perimee" % (ours, cli_total))
    return "CLI %.4f USD, notre instrument %.4f USD" % (cli_total, ours)


def t_table_de_prix_contre_facturation_reelle():
    """Ferme la boucle : notre calcul contre la comptabilite du CLI.

    Exige un sous-agent en PREMIER PLAN. Un sous-agent de fond ne rapporte
    qu'un total, sans ventilation : le cout devient incalculable et la
    comparaison impossible. Claude Code choisit l'arriere-plan par defaut,
    il faut donc le demander explicitement.
    """
    env = claude(
        "Utilise l'outil Agent avec subagent_type 'scout' en PREMIER PLAN, "
        "c'est-a-dire avec run_in_background a false, pour compter les "
        "fichiers .md a la racine du depot. Attends sa reponse, donne le "
        "nombre, et termine.")
    assert_authenticated(env)
    sid = env.get("session_id")
    assert sid, "pas de session_id dans l'enveloppe"
    cli_cost = env.get("total_cost_usd") or 0
    assert cli_cost > 0, "le CLI n'a rapporte aucun cout"

    slug = ROOT.replace("\\", "-").replace("/", "-").replace(":", "-")
    sessions_dir = os.path.join(os.environ["USERPROFILE"],
                                ".claude", "projects", slug)
    export = os.path.join(ROOT, "_smoketest_prix.json")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         os.path.join(ROOT, "extract_claude_jsonl.ps1"),
         "-SessionsDir", sessions_dir, "-SessionId", sid,
         "-ExportPath", export, "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-600:]
    with open(export, encoding="utf-8-sig") as fh:
        report = json.load(fh)

    assert report["Complete"], \
        "session non observable : %s" % report["Diagnostics"][:3]

    ours = report["TotalCostUsd"]
    ratio = ours / cli_cost
    assert 0.95 <= ratio <= 1.05, \
        ("notre table donne %.6f USD, le CLI facture %.6f USD (rapport %.3f). "
         "Table de prix perimee, ou extraction incomplete."
         % (ours, cli_cost, ratio))

    # Preuve que l'effort du role s'applique : il est lu dans le transcript du
    # sous-agent, pas declare par lui.
    roles = [b for b in report["Buckets"] if b["Kind"].startswith("sous-agent")]
    assert roles, "aucun sous-agent dans le rapport"
    scout = [b for b in roles if b["Key"] == "scout"]
    assert scout, "scout absent du rapport : %s" % [b["Key"] for b in roles]
    assert scout[0]["Effort"] == "medium", \
        ("effort effectif de scout = '%s', attendu 'medium' (valeur du role)"
         % scout[0]["Effort"])
    assert "sonnet" in scout[0]["Model"], \
        "modele effectif de scout = %s" % scout[0]["Model"]

    return ("CLI %.6f USD, notre instrument %.6f USD, rapport %.3f ; "
            "scout observe en %s effort %s"
            % (cli_cost, ours, ratio, scout[0]["Model"], scout[0]["Effort"]))


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Ce harness requiert Windows PowerShell 5.1.")
        sys.exit(1)

    print("Depot teste : %s" % ROOT)
    print("Ces tests consomment du budget reel. Aucun n'utilise Fable.\n")
    print("Niveau 3 - comportement reel")

    tests = [t_session_demarre,
             t_role_scout_est_lance_et_resolu_en_sonnet,
             t_scout_ne_peut_pas_ecrire,
             t_un_role_ne_redelegue_pas,
             t_table_de_prix_contre_facturation_reelle]
    for test in tests:
        check(test.__name__[2:].replace("_", " "), test)

    total_cost = sum(r.get("total_cost_usd") or 0 for r in runs)
    print("\n%d session(s), cout total rapporte par le CLI : %.4f USD"
          % (len(runs), total_cost))

    if failures:
        print("%d ECHEC(S) sur %d tests" % (len(failures), len(tests)))
        sys.exit(1)
    print("%d tests passes." % len(tests))
