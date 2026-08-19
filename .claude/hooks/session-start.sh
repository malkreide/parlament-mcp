#!/usr/bin/env bash
#
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<Standard-Branch> liegt.
#
# GRUND: Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt,
# deren Ursache nicht im Diff stand — die fehlenden Commits waren jeweils
# genau die, die das Gate einfuehrten, an dem der Branch scheiterte. Die
# Pruefung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
# Dateien.
#
# OBERSTE REGEL: Der Hook blockiert die Session NIEMALS. Kein Netz, kein
# Remote, detached HEAD, flatterndes DNS, kein git — jeder dieser Faelle geht
# still durch (Exit 0, keine Ausgabe). Ein Hook, der bei Netzproblemen die
# Arbeit anhaelt, wird nach dem zweiten Mal abgeschaltet und schuetzt danach
# gar nichts.
#
# Ausgabe gibt es nur, wenn tatsaechlich Commits fehlen. Bei 0 schweigt er.

# Kein `set -e`: ein fehlschlagender Teilschritt darf hier nichts abbrechen,
# er fuehrt zum stillen Durchgang.
set -u

# Sekunden, die eine Netzoperation hoechstens dauern darf.
NETZ_TIMEOUT="${PARLAMENT_HOOK_TIMEOUT:-5}"

# Unter keinen Umstaenden interaktiv nach Zugangsdaten fragen — ein
# wartender Prompt ist genau das Blockieren, das hier ausgeschlossen ist.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=true
export SSH_ASKPASS=true
export SSH_ASKPASS_REQUIRE=never
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes -o ConnectTimeout=${NETZ_TIMEOUT} -o StrictHostKeyChecking=accept-new}"
export GIT_CONFIG_PARAMETERS="'credential.helper='"

# Mit Zeitlimit ausfuehren. `timeout` gibt es nicht ueberall (macOS ohne
# coreutils); dann uebernimmt der Shell-Nachbau. Rueckgabe 124 = Zeit um.
mit_zeitlimit() {
  local sekunden="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "${sekunden}" "$@"
    return $?
  fi
  "$@" &
  local pid=$!
  local gewartet=0
  while kill -0 "${pid}" 2>/dev/null; do
    if [ "${gewartet}" -ge "${sekunden}" ]; then
      kill -TERM "${pid}" 2>/dev/null
      wait "${pid}" 2>/dev/null
      return 124
    fi
    sleep 1
    gewartet=$((gewartet + 1))
  done
  wait "${pid}"
}

# Ab hier ist jeder Fehlschlag ein Grund zu schweigen, nicht zu meckern.
command -v git >/dev/null 2>&1 || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Unborn HEAD (frisch initialisiertes Repo) hat nichts zu vergleichen.
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || exit 0

# Kein Remote namens origin -> nichts zu pruefen.
git remote get-url origin >/dev/null 2>&1 || exit 0

# Standard-Branch ermitteln, NICHT `main` annehmen: drei Server im Portfolio
# heissen ihren Standard-Branch `master`. Genau diese Annahme hat schon einmal
# einen Branch 15 Commits alt werden lassen.
# Erst die lokal gecachte Notiz (kostet kein Netz), dann die Quelle fragen.
standard_branch="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)"
standard_branch="${standard_branch#origin/}"

if [ -z "${standard_branch}" ]; then
  standard_branch="$(
    mit_zeitlimit "${NETZ_TIMEOUT}" git ls-remote --symref origin HEAD 2>/dev/null |
      sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' |
      head -1
  )"
fi

# Ohne Standard-Branch wird hier nichts geraten — lieber schweigen.
[ -n "${standard_branch}" ] || exit 0

# Den Standard-Branch holen. Schlaegt das fehl oder laeuft es in das
# Zeitlimit (kein Netz, flatterndes DNS, Remote weg), ist die Session fertig.
mit_zeitlimit "${NETZ_TIMEOUT}" git fetch --quiet origin "${standard_branch}" >/dev/null 2>&1 || exit 0

# FETCH_HEAD ist der eben geholte Stand. Ohne ihn gibt es nichts zu zaehlen.
git rev-parse --verify --quiet FETCH_HEAD >/dev/null 2>&1 || exit 0

# Wie viele Commits von origin/<Standard-Branch> fehlen im ausgecheckten
# Stand? Funktioniert auch bei detached HEAD.
rueckstand="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"

# Nur eine reine Zahl ist ein Ergebnis.
case "${rueckstand}" in
  '' | *[!0-9]*) exit 0 ;;
esac

# Bei 0 schweigt der Hook.
[ "${rueckstand}" -gt 0 ] || exit 0

commit_wort="Commits"
[ "${rueckstand}" -eq 1 ] && commit_wort="Commit"

hier="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
[ "${hier}" = "HEAD" ] && hier="detached HEAD"

cat <<MELDUNG
Klon-Aktualitaet: Der ausgecheckte Stand (${hier}) liegt ${rueckstand} ${commit_wort} hinter origin/${standard_branch}.

Vor der Arbeit den Rueckstand aufholen:
  auf dem Standard-Branch:  git merge --ff-only FETCH_HEAD
  auf einem Feature-Branch: git merge origin/${standard_branch}

Grund: Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff
steht — am 3.8.2026 zweimal passiert, beide Male fehlten genau die Commits,
die das Gate einfuehrten, an dem der Branch scheiterte.
MELDUNG

exit 0
