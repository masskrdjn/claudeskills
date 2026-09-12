"""Auto-controle de extract_claude_jsonl.ps1.

Run with Python stdlib + Windows PowerShell 5.1. No model calls.
Fabrique l'arborescence de transcripts que produit Claude Code, invoque le
script, verifie le rapport. Le contrat teste est celui dont depend toute la
doctrine : Complete = true seulement en l'absence de diagnostic, et cout exact
sinon rien.

Plusieurs attentes chiffrees viennent d'une facturation reelle observee, citee
dans le test concerne. Ce sont les seules valeurs qui font autorite ici.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "extract_claude_jsonl.ps1")
SESSION = "sess-a"


def usage(inp, out, cw_5m, cr, cw_1h=0):
    """`cw_5m` est une ecriture de cache 5 minutes, `cw_1h` une ecriture 1 heure.

    Les deux se tarifent differemment : 1,25x l'entree contre 2x.
    """
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_creation_input_tokens": cw_5m + cw_1h,
        "cache_creation": {"ephemeral_5m_input_tokens": cw_5m,
                           "ephemeral_1h_input_tokens": cw_1h},
        "cache_read_input_tokens": cr,
    }


def turn(model, msg_id, inp, out, cw_5m, cr, cw_1h=0, effort=None,
         block="text"):
    rec = {
        "type": "assistant",
        "timestamp": "2026-09-12T10:00:00.000Z",
        "message": {"id": msg_id, "model": model, "role": "assistant",
                    "content": [{"type": block}],
                    "usage": usage(inp, out, cw_5m, cr, cw_1h)},
    }
    if effort:
        rec["effort"] = effort
    return rec


def agent_call(agent_id, agent_type, status="completed", duration=1000,
               tool_uses=3, usage_override=None):
    """Le resultat d'appel : metriques d'appel, et un `usage` trompeur.

    Ce champ ne porte que le dernier tour du sous-agent ; le script ne doit
    jamais s'en servir pour le cout.
    """
    return {
        "type": "user",
        "timestamp": "2026-09-12T10:05:00.000Z",
        "toolUseResult": {
            "agentId": agent_id,
            "agentType": agent_type,
            "resolvedModel": "peu-importe",
            "status": status,
            "totalDurationMs": duration,
            "totalToolUseCount": tool_uses,
            "usage": usage_override or usage(1, 1, 0, 0),
        },
    }


def run(root_records, subagents=(), raw_lines=(), session_id=SESSION):
    """Ecrit l'arborescence, lance le script, rend le rapport parse.

    `subagents` : sequence de (agent_id, meta_or_None, [enregistrements]).
    """
    tmp = tempfile.mkdtemp(prefix="claudejsonl_")
    with open(os.path.join(tmp, session_id + ".jsonl"), "w",
              encoding="utf-8") as fh:
        for rec in root_records:
            fh.write(json.dumps(rec) + "\n")
        for line in raw_lines:
            fh.write(line + "\n")

    if subagents:
        subdir = os.path.join(tmp, session_id, "subagents")
        os.makedirs(subdir)
        for agent_id, meta, records in subagents:
            base = os.path.join(subdir, "agent-%s" % agent_id)
            with open(base + ".jsonl", "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec) + "\n")
            if meta is not None:
                with open(base + ".meta.json", "w", encoding="utf-8") as fh:
                    json.dump(meta, fh)

    export = os.path.join(tmp, "report.json")
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", SCRIPT, "-SessionsDir", tmp, "-ExportPath", export, "-Quiet"],
        capture_output=True, text=True)
    assert proc.returncode == 0, (
        "script en echec (code %s)\nSTDOUT:\n%s\nSTDERR:\n%s"
        % (proc.returncode, proc.stdout, proc.stderr))
    with open(export, encoding="utf-8-sig") as fh:  # PowerShell 5.1 ecrit un BOM
        report = json.load(fh)
    shutil.rmtree(tmp, ignore_errors=True)
    return report


def meta(agent_type, shape="foreground"):
    return {"agentType": agent_type, "requestShape": shape, "spawnDepth": 1}


def bucket(report, key):
    found = [b for b in report["Buckets"] if b["Key"] == key]
    assert len(found) == 1, \
        "attendu 1 bucket '%s', trouve %d : %s" % (key, len(found),
                                                   [b["Key"] for b in report["Buckets"]])
    return found[0]


# --- Contrat de base -------------------------------------------------------

def test_schema_et_run_complet():
    report = run(
        [turn("claude-opus-5", "m1", 1000, 500, 2000, 4000, effort="xhigh")],
        subagents=[("aaa", meta("scout"),
                    [turn("claude-sonnet-5", "s1", 10000, 2000, 0, 50000,
                          effort="medium")])])
    assert report["SchemaVersion"] == 2
    assert report["Complete"] is True, report["Diagnostics"]

    # 1000/1e6*5 + 500/1e6*25 + 2000/1e6*6.25 + 4000/1e6*0.50
    racine = bucket(report, "racine")
    assert abs(racine["CostUsd"] - 0.032) < 1e-9, racine["CostUsd"]
    assert racine["Effort"] == "xhigh"

    # 10000/1e6*2 + 2000/1e6*10 + 0 + 50000/1e6*0.20
    scout = bucket(report, "scout")
    assert abs(scout["CostUsd"] - 0.05) < 1e-9, scout["CostUsd"]
    assert scout["Effort"] == "medium", "l'effort du role doit etre lisible"
    assert scout["Kind"] == "sous-agent (foreground)"
    assert abs(report["TotalCostUsd"] - 0.082) < 1e-9, report["TotalCostUsd"]


# --- Les deux pieges verifies contre la facturation reelle -----------------

def test_usage_cumulatif_on_retient_le_maximum():
    """Un message s'etale sur plusieurs enregistrements, usage cumulatif.

    Observe en session reelle : le bloc `thinking` porte out=2, le bloc `text`
    du MEME message porte out=198. Retenir le premier sous-compte la sortie.
    """
    report = run([
        turn("claude-sonnet-5", "m1", 2, 2, 235, 8709, block="thinking"),
        turn("claude-sonnet-5", "m1", 2, 198, 235, 8709, block="text"),
    ])
    b = bucket(report, "racine")
    assert b["Turns"] == 1, "le message a ete compte deux fois"
    assert b["OutputTokens"] == 198, \
        "sortie %d, attendu 198 (le maximum, pas le premier)" % b["OutputTokens"]
    assert b["CacheWrite5mTokens"] == 235, "le cache a ete additionne deux fois"


def test_cout_du_sous_agent_vient_de_son_transcript():
    """`toolUseResult.usage` ne porte que le dernier tour : il ne doit pas servir.

    Ici le resultat d'appel annonce un usage derisoire, tandis que le
    transcript du sous-agent porte deux tours. Le cout doit suivre le transcript.
    """
    report = run(
        [turn("claude-opus-5", "m1", 10, 10, 0, 0),
         agent_call("aaa", "scout", usage_override=usage(2, 198, 235, 8709))],
        subagents=[("aaa", meta("scout"), [
            turn("claude-sonnet-5", "s1", 2, 87, 5255, 3454, effort="medium"),
            turn("claude-sonnet-5", "s2", 2, 198, 235, 8709, effort="medium"),
        ])])
    assert report["Complete"] is True, report["Diagnostics"]
    scout = bucket(report, "scout")
    assert scout["Turns"] == 2, "les deux tours doivent etre comptes"
    assert scout["OutputTokens"] == 285, \
        "sortie %d, attendu 285 (87+198)" % scout["OutputTokens"]
    # Facturation reelle observee pour exactement ces tokens : 0.0190156 USD.
    assert abs(scout["CostUsd"] - 0.0190156) < 1e-6, \
        "cout %.7f, facturation reelle 0.0190156" % scout["CostUsd"]
    assert scout["DurationMs"] == 1000, "metriques d'appel perdues"


def test_cache_une_heure_coute_deux_fois_l_entree():
    """Facturation reelle : Haiku, 18 entree / 436 sortie / 8626 cache 1h /
    60598 lecture de cache = 0.0255098 USD."""
    report = run([turn("claude-haiku-4-5-20251001", "m1", 18, 436, 0, 60598,
                       cw_1h=8626, effort="medium")])
    assert report["Complete"] is True, report["Diagnostics"]
    b = bucket(report, "racine")
    assert b["CacheWrite1hTokens"] == 8626 and b["CacheWrite5mTokens"] == 0
    assert abs(b["CostUsd"] - 0.0255098) < 1e-6, \
        "cout %.7f, facturation reelle 0.0255098" % b["CostUsd"]


def test_cache_cinq_minutes_coute_1_25_fois_l_entree():
    """Facturation reelle : Sonnet, 4 / 285 / 5490 cache 5m / 12163 = 0.0190156."""
    report = run([turn("claude-sonnet-5", "m1", 4, 285, 5490, 12163)])
    b = bucket(report, "racine")
    assert abs(b["CostUsd"] - 0.0190156) < 1e-6, \
        "cout %.7f, facturation reelle 0.0190156" % b["CostUsd"]


# --- Refus de chiffrer ------------------------------------------------------

def test_ecriture_de_cache_sans_ttl_interdit_le_cout():
    rec = turn("claude-opus-5", "m1", 100, 50, 5000, 0)
    del rec["message"]["usage"]["cache_creation"]
    report = run([rec])
    assert report["Complete"] is False
    assert any("duree de vie" in d for d in report["Diagnostics"]), \
        report["Diagnostics"]
    assert report["TotalCostUsd"] is None


def test_ligne_illisible_rend_le_run_non_observable():
    report = run([turn("claude-opus-5", "m1", 100, 50, 0, 0)],
                 raw_lines=["{ceci n'est pas du JSON"])
    assert report["Complete"] is False
    assert any("illisible" in d for d in report["Diagnostics"]), \
        report["Diagnostics"]


def test_modele_inconnu_ne_produit_pas_de_cout():
    report = run([turn("claude-mystere-9", "m1", 100, 50, 0, 0)])
    assert report["Complete"] is False
    assert any("table de prix" in d for d in report["Diagnostics"]), \
        report["Diagnostics"]
    assert bucket(report, "racine")["CostUsd"] is None
    assert report["TotalCostUsd"] is None


def test_sous_agent_sans_transcript_est_signale():
    report = run([turn("claude-opus-5", "m1", 10, 10, 0, 0),
                  agent_call("fantome", "researcher")])
    assert report["Complete"] is False
    assert any("sans transcript" in d for d in report["Diagnostics"]), \
        report["Diagnostics"]


def test_sous_agent_non_termine_est_signale():
    report = run(
        [turn("claude-opus-5", "m1", 10, 10, 0, 0),
         agent_call("aaa", "runner", status="failed")],
        subagents=[("aaa", meta("runner"),
                    [turn("claude-haiku-4-5", "s1", 10, 10, 0, 0)])])
    assert report["Complete"] is False
    assert any("failed" in d for d in report["Diagnostics"]), report["Diagnostics"]


def test_meta_absent_empeche_l_attribution():
    report = run([turn("claude-opus-5", "m1", 10, 10, 0, 0)],
                 subagents=[("aaa", None,
                             [turn("claude-sonnet-5", "s1", 10, 10, 0, 0)])])
    assert report["Complete"] is False
    assert any("non attribuable" in d for d in report["Diagnostics"]), \
        report["Diagnostics"]


# --- Divers -----------------------------------------------------------------

def test_agent_de_fond_est_mesurable():
    """Un sous-agent de fond a son transcript comme les autres : il est chiffrable."""
    report = run([turn("claude-opus-5", "m1", 10, 10, 0, 0)],
                 subagents=[("bbb", meta("researcher", shape="background"),
                             [turn("claude-sonnet-5", "s1", 1000, 100, 0, 0,
                                   effort="medium")])])
    assert report["Complete"] is True, report["Diagnostics"]
    b = bucket(report, "researcher")
    assert b["Kind"] == "sous-agent (background)"
    assert abs(b["CostUsd"] - (1000 / 1e6 * 2 + 100 / 1e6 * 10)) < 1e-9


def test_identifiant_date_apparie_par_prefixe():
    report = run([turn("claude-haiku-4-5-20251001", "m1", 20000, 3000, 0, 0)])
    assert report["Complete"] is True, report["Diagnostics"]
    # 20000/1e6*1 + 3000/1e6*5
    assert abs(bucket(report, "racine")["CostUsd"] - 0.035) < 1e-9


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Ce harness requiert Windows PowerShell 5.1.")
        sys.exit(1)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print("ok  %s" % test.__name__)
    print("\n%d tests passes." % len(tests))
