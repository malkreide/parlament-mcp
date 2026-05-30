# Security Posture — parlament-mcp

Dieses Dokument fasst die sicherheitsrelevanten Designentscheidungen zusammen
und referenziert die Audit-Findings aus dem `mcp-audit-skill`-Lauf.

## Profil

| Eigenschaft | Wert |
|---|---|
| Transport | stdio (Default) + Streamable HTTP (Cloud) |
| Auth-Modell | keines (öffentliche, schreibgeschützte Daten) |
| Datenklasse | Public Open Data (BGÖ — öffentliche Amtshandlungen) |
| Schreibzugriff | read-only |
| Datenquelle | Curia Vista / ws.parlament.ch (CC BY 4.0) |

## Lethal Trifecta — Bewertung (SEC-019)

Simon Willisons «Lethal Trifecta»: gefährlich wird ein Server erst, wenn er
**alle drei** Fähigkeiten vereint.

| Fähigkeit | Status | Begründung |
|---|:--:|---|
| Zugriff auf private Daten | ❌ Nein | Ausschliesslich Public Open Data (Curia Vista). Keine PII, keine Verwaltungs-Innendaten. |
| Exposition gegenüber untrusted Content | ⚠️ Begrenzt | Liest nur die feste, vertrauenswürdige Curia-Vista-API; keine User-Uploads, kein Web-Scraping beliebiger Seiten. |
| Externe Kommunikation / Write | ❌ Nein | Read-only; alle Tools `readOnlyHint: true`. Kein Mail-/Webhook-/POST-Versand. |

**Trifecta-Score: ~1 von 3 → sicher.** Eine Datenexfiltration via
Prompt-Injection ist strukturell nicht möglich, weil der Server weder private
Daten liest noch nach extern senden kann. Siehe auch
[`adr/ADR-001-server-separation.md`](adr/ADR-001-server-separation.md).

## Netzwerk-Bindung (SEC-016)

- Default-Bind: `127.0.0.1` (nur localhost).
- `0.0.0.0` nur via explizitem `MCP_HOST=0.0.0.0` und nur im Container-Kontext;
  ausserhalb eines erkannten Containers wird eine NeighborJack-Warnung geloggt.

## Egress-Allow-List (SEC-021)

Defense-in-Depth in zwei Layern:

1. **Code-Layer:** `parlament_mcp.security.ALLOWED_HOSTS` (frozenset) — jeder
   ausgehende Request wird via `assert_host_allowed()` geprüft. Einzig erlaubter
   Host: `ws.parlament.ch`.
2. **Network-Layer:** Kubernetes `NetworkPolicy` (siehe
   [`network-egress.md`](network-egress.md) und `deploy/k8s/networkpolicy.yaml`) —
   nur HTTPS/443 + DNS nach aussen, interne Ranges (Cloud-Metadata, RFC1918)
   blockiert.

## Session-Handling (SEC-009)

Im HTTP-Transport vergibt das MCP-SDK kryptografisch sichere `Mcp-Session-Id`s.
Ein Binding an eine **authentifizierte** User-Identität ist im aktuellen
No-Auth-Profil nicht möglich — und auch nicht nötig: der Server liefert
ausschliesslich öffentliche, read-only Daten, ein Session-Hijack erlaubt also
keinen Zugriff, den ein Angreifer nicht ohnehin hätte. **Sobald Auth/Write
hinzukommt (Phase 3), wird User-gebundenes Session-Binding verpflichtend.**

## MCP-Gateway: Tool-Allow-Listing & Poisoning-Detection (SEC-014/SEC-015)

Im aktuellen Single-Server-Setup mit ausschliesslich eigenen, vertrauenswürdigen
Tools ist das Risiko niedrig. Für den Multi-Server-/Gateway-Fall liefert das
Repo wiederverwendbare Bausteine:

- `parlament_mcp.gateway.filter_allowed_tools()` — Default-Deny Tool-Allow-List
  (Beispiel-Config: `gateway/tool-allowlist.example.yaml`).
- `parlament_mcp.gateway.scan_tool_definition()` / `filter_tool_list()` —
  Pre-Flight Tool-Poisoning-Detection (System-Prompts, Override-Phrasen DE/EN/FR,
  Zero-Width-Zeichen, Homoglyphs, verdächtige URLs, Überlänge).

Diese werden aktiviert, sobald externe MCP-Server in ein gemeinsames Gateway
integriert werden.

## Tool-Definition-Pinning (SEC-022)

- Konsistenter `parlament_`-Namespace auf allen Tools → kein Cross-Server-Shadowing.
- `tool-hashes.json` pinnt SHA-256 aller Tool-Definitionen; die CI
  (`.github/workflows/security.yml`) verifiziert bei jedem PR, dass sich
  Tool-Definitionen nicht unbemerkt ändern (Rug-Pull-Schutz). Änderungen müssen
  im CHANGELOG dokumentiert werden (Re-Approval-Hinweis).

## Secret-Scanning (ARCH-005 / SEC-013)

Der Server nutzt keinerlei Secrets (öffentliche API, keine Auth). Trotzdem läuft
gitleaks in CI als Regressionsschutz, und PyPI-Releases nutzen OIDC-Trusted-
Publisher (kein langlebiger Token).
