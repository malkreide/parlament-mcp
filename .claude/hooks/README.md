# SessionStart-Hook: Klon-Aktualitaet

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<Standard-Branch>` liegt.

## Grund

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einfuehrten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den Dateien, die man selbst angefasst hat, und findet ihn dort nicht.
Die Pruefung kostet eine Sekunde und ersetzt diese Fehlersuche in den
falschen Dateien.

Die Pruefung selbst steht schon als Handgriff in `CLAUDE.md` («Vor der
Arbeit»). Ein Handgriff, an den man denken muss, wird vergessen — genau
zweimal am 3.8.2026. Der Hook macht daraus etwas, das von allein passiert.

## Verhalten

- **Blockiert nie.** Kein `git`, kein Repo, kein `origin`, kein Netz,
  flatterndes DNS, Zeitlimit abgelaufen, unborn oder detached HEAD: jeder
  dieser Faelle endet still mit Exit 0 und ohne Ausgabe. Ein Hook, der bei
  Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet
  und schuetzt danach gar nichts.
- **Fragt nie nach Zugangsdaten.** `GIT_TERMINAL_PROMPT=0`, leerer
  Credential-Helper und `ssh -o BatchMode=yes`: ein wartender Passwort-Prompt
  waere genau das Blockieren, das hier ausgeschlossen ist.
- **Kurzes Zeitlimit** auf jede Netzoperation (`ls-remote`, `fetch`),
  Vorgabe 5 Sekunden, per `PARLAMENT_HOOK_TIMEOUT` verstellbar. Zusaetzlich
  begrenzt `.claude/settings.json` den ganzen Hook auf 15 Sekunden.
  `timeout` wird benutzt, wenn vorhanden; sonst greift ein Shell-Nachbau
  (macOS ohne coreutils).
- **Schweigt bei 0.** Ausgabe gibt es nur, wenn tatsaechlich Commits fehlen.
- **Ermittelt den Standard-Branch, statt `main` anzunehmen.** Drei Server im
  Portfolio (`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`) heissen ihren
  Standard-Branch `master`; die Annahme `main` hat dort schon einmal einen
  Branch 15 Commits alt werden lassen. Zuerst wird die lokal gecachte Notiz
  `refs/remotes/origin/HEAD` gelesen (kostet kein Netz), erst danach
  `git ls-remote --symref origin HEAD` gefragt. Laesst sich der Branch nicht
  ermitteln, wird nichts geraten — dann schweigt der Hook.

## Von Hand pruefen

```bash
CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/session-start.sh; echo "Exit: $?"
```

Auf aktuellem Stand: keine Ausgabe, Exit 0. Einen Rueckstand kann man
herstellen, ohne etwas kaputtzumachen:

```bash
git switch --detach HEAD~3   # 3 Commits zurueck
CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/session-start.sh
git switch -                 # zurueck
```
