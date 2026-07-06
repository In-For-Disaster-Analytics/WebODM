#!/bin/bash
# WebODM backup control -- manage the corral-safe backup WITHOUT running the full setup.sh
# (which rebuilds containers, rewrites nginx/firewall, etc.). Standalone and idempotent.
#
# Usage:
#   scripts/backup-ctl.sh install       Install/refresh /usr/local/bin/webodm-backup.sh (+ logrotate).
#                                         Does NOT schedule the cron.
#   scripts/backup-ctl.sh enable-cron   Schedule the nightly job (0 2 * * *).
#   scripts/backup-ctl.sh disable-cron  Remove the cron line.
#   scripts/backup-ctl.sh run           Run a backup now (foreground), for testing.
#   scripts/backup-ctl.sh status        Show install/cron/log/alert + any stuck (D-state) processes.
#   scripts/backup-ctl.sh uninstall     Remove the cron, script, and logrotate config.
#
# See docs/design/2026-07-01-backup-hardening-corral-safe.md and
#     docs/incidents/2026-06-17-corral-backup-io-outage.md
set -euo pipefail

TARGET="/usr/local/bin/webodm-backup.sh"
LOGROTATE="/etc/logrotate.d/webodm-backup"
LOG_FILE="/var/log/webodm-backup.log"
ALERT_FILE="/var/log/webodm-backup.failed"
CRON_LINE="0 2 * * * $TARGET"

log() { printf '%s\n' "$*"; }

install_script() {
    log "Installing corral-safe backup script -> $TARGET"
    sudo tee "$TARGET" > /dev/null << 'EOF'
#!/bin/bash
# WebODM corral-safe backup.
# Principles: never hang the mount, fail loudly (never fake success), throttle I/O,
# stage the DB dump locally, back up media incrementally to a separate corral subtree.
set -euo pipefail

# --- Config (override via environment) ---------------------------------------
MEDIA_ROOT="${WEBODM_MEDIA_ROOT:-/corral/webodm/media}"       # live media (read-only here)
BACKUP_DIR="${WEBODM_BACKUP_DIR:-/corral/webodm/backups}"     # corral subtree, NOT the media tree
MEDIA_BACKUP_DIR="$BACKUP_DIR/media"                          # rsync mirror target
DB_STAGE_DIR="${WEBODM_DB_STAGE:-$HOME/ODM-SUITE/backups/db}" # LOCAL disk staging for the DB dump

# Derive the DB name/user from WebODM's OWN config so the backup always targets the DB
# the app actually uses. WebODM's settings.py falls back to these same defaults
# (WO_DATABASE_NAME=webodm_dev, WO_DATABASE_USER=postgres) when unset. As of 2026-07 no
# WO_DATABASE_NAME override is set, so this resolves to WebODM's shipped default
# "webodm_dev" -- a known-unintended prod DB name, tracked separately for rename. When
# WO_DATABASE_NAME is eventually set, this backup follows it automatically (no drift).
WEBODM_ENV="${WEBODM_ENV_FILE:-$HOME/ODM-SUITE/WebODM/.env}"
env_val() { [[ -f "$WEBODM_ENV" ]] || return 0; grep -E "^$1=" "$WEBODM_ENV" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
DB_NAME="${WEBODM_DB:-$(env_val WO_DATABASE_NAME)}"; DB_NAME="${DB_NAME:-webodm_dev}"
DB_USER="${WEBODM_DB_USER:-$(env_val WO_DATABASE_USER)}"; DB_USER="${DB_USER:-postgres}"
LOG_FILE="${WEBODM_BACKUP_LOG:-/var/log/webodm-backup.log}"
ALERT_FILE="${WEBODM_BACKUP_ALERT:-/var/log/webodm-backup.failed}"
RETENTION_DAYS="${WEBODM_BACKUP_RETENTION_DAYS:-7}"
PREFLIGHT_TIMEOUT="${WEBODM_PREFLIGHT_TIMEOUT:-20}"           # seconds
DB_TIMEOUT="${WEBODM_DB_TIMEOUT:-1800}"                       # seconds (30m)
MEDIA_TIMEOUT="${WEBODM_MEDIA_TIMEOUT:-6h}"

DATE=$(date +%Y%m%d_%H%M%S)

log() { printf '%s [%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$1" "${2:-}" | tee -a "$LOG_FILE" 2>/dev/null >&2 || true; }
fail() { log ERROR "$1"; date +'%Y-%m-%d %H:%M:%S' > "$ALERT_FILE" 2>/dev/null || true; echo "$1" >> "$ALERT_FILE" 2>/dev/null || true; exit 1; }

# --- Single-instance lock (a slow/stuck run must NOT stack another) ----------
# Prefer /var/lock, but fall back to /tmp so the lock never blocks the run just
# because of directory permissions (this script runs as an unprivileged user).
LOCK_FILE="${WEBODM_LOCK:-/var/lock/webodm-backup.lock}"
if ! exec 9>"$LOCK_FILE" 2>/dev/null; then
    LOCK_FILE="/tmp/webodm-backup.lock"
    exec 9>"$LOCK_FILE" || fail "cannot open lock file ($LOCK_FILE)"
fi
if ! flock -n 9; then
    log WARN "another backup run holds the lock; exiting without stacking"
    exit 0
fi

log INFO "backup start (DATE=$DATE, DB=$DB_NAME)"

# --- Preflight: corral must be mounted, writable, and responsive -------------
# Never proceed into a hard-NFS hang; skip-and-alert instead.
corral_ok() {
    mountpoint -q /corral || { log ERROR "corral is not a mountpoint"; return 1; }
    timeout "$PREFLIGHT_TIMEOUT" mkdir -p "$BACKUP_DIR" 2>/dev/null || { log ERROR "cannot create $BACKUP_DIR (timeout/denied)"; return 1; }
    local probe="$BACKUP_DIR/.write_test.$$"
    timeout "$PREFLIGHT_TIMEOUT" bash -c "touch '$probe' && rm -f '$probe'" 2>/dev/null || { log ERROR "corral not writable within ${PREFLIGHT_TIMEOUT}s"; return 1; }
    return 0
}
corral_ok || fail "corral preflight failed; skipping backup (mount down or Permission denied)"

# --- Database backup: stage LOCALLY, verify, then copy to corral -------------
# Local staging means the DB backup survives even a corral outage.
# NOTE: container name "db" is fixed by docker-compose.yml (container_name: db);
# if that ever changes this fails loudly (below) rather than silently skipping.
db_ok=false
if docker ps --format '{{.Names}}' | grep -qx db; then
    mkdir -p "$DB_STAGE_DIR"
    stage="$DB_STAGE_DIR/${DB_NAME}_$DATE.dump"
    if timeout "$DB_TIMEOUT" docker exec db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$stage"; then
        # pg_restore --list is a structural/TOC integrity check (archive is readable),
        # NOT a full restore drill; schedule periodic test-restores separately.
        if [[ -s "$stage" ]] && docker exec -i db pg_restore --list < "$stage" >/dev/null 2>&1; then
            # timeout-wrapped: corral was healthy at preflight, but pg_dump may have
            # run for up to DB_TIMEOUT since then, so re-guard this corral write.
            if timeout 300 cp "$stage" "$BACKUP_DIR/${DB_NAME}_$DATE.dump"; then
                log INFO "database backed up: $BACKUP_DIR/${DB_NAME}_$DATE.dump ($(du -h "$stage" | cut -f1))"
                db_ok=true
            else
                fail "copy of DB dump to corral failed or timed out (mount may have degraded mid-run)"
            fi
        else
            rm -f "$stage"; fail "pg_dump produced an empty or unrestorable dump for '$DB_NAME'"
        fi
    else
        rm -f "$stage"; fail "pg_dump failed or timed out for database '$DB_NAME'"
    fi
    # Prune local staging so it cannot fill local disk and stall Postgres.
    timeout 5m find "$DB_STAGE_DIR" -type f -name '*.dump' -mtime "+$RETENTION_DAYS" -delete || log WARN "local staging prune timed out"
else
    fail "db container not running; cannot back up database"
fi

# --- Media backup: incremental, throttled, time-boxed, point-in-time ---------
# Dated hardlink snapshots (--link-dest against the previous snapshot): unchanged
# files are hardlinked so each snapshot costs ~the delta, but every night is an
# independent, immutable point-in-time copy. This means a bad night in the live
# tree (accidental deletion, partial/empty listing during a flaky mount) does NOT
# destroy older backups the way a single --delete'd mirror would.
# Runs in the idle I/O class so it yields to WebODM; time-boxed so a stuck copy
# is killed rather than left hanging the mount.
media_ok=false
if [[ -d "$MEDIA_ROOT" ]]; then
    snap_dir="$MEDIA_BACKUP_DIR/$DATE"
    latest_link="$MEDIA_BACKUP_DIR/latest"
    mkdir -p "$MEDIA_BACKUP_DIR"
    link_dest=()
    [[ -d "$latest_link" ]] && link_dest=(--link-dest="$latest_link")
    if timeout "$MEDIA_TIMEOUT" ionice -c3 nice -n19 \
         rsync -a --delete --partial "${link_dest[@]}" "$MEDIA_ROOT/" "$snap_dir/"; then
        # Atomically repoint "latest" at the new snapshot for the next --link-dest base.
        ln -sfn "$snap_dir" "$latest_link.tmp" && mv -Tf "$latest_link.tmp" "$latest_link"
        log INFO "media snapshot: $snap_dir"
        media_ok=true
    else
        fail "media rsync failed or timed out (${MEDIA_TIMEOUT})"
    fi
else
    log WARN "media root $MEDIA_ROOT not found; skipping media backup"
fi

# --- Retention (time-boxed): prune old DB dumps AND old media snapshots ------
# Keep enough media snapshots for several recovery points, not just one.
timeout 10m find "$BACKUP_DIR" -maxdepth 1 -type f -mtime "+$RETENTION_DAYS" -delete || log WARN "corral db-dump retention sweep timed out"
timeout 10m find "$MEDIA_BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf {} + || log WARN "media snapshot retention sweep timed out"

rm -f "$ALERT_FILE" 2>/dev/null || true
log INFO "backup complete (db_ok=$db_ok, media_ok=$media_ok)"
EOF

    sudo chmod +x "$TARGET"

    sudo tee "$LOGROTATE" > /dev/null << 'EOF'
/var/log/webodm-backup.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
    sudo touch "$LOG_FILE"
    sudo chown "$(id -un)":"$(id -gn)" "$LOG_FILE" 2>/dev/null || true
    log "Installed. Cron NOT scheduled -- run '$0 enable-cron' when corral is healthy."
}

enable_cron() {
    [[ -x "$TARGET" ]] || { log "ERROR: $TARGET not installed; run '$0 install' first"; exit 1; }
    if crontab -l 2>/dev/null | grep -q "webodm-backup"; then
        log "Cron already present; leaving as-is:"
        crontab -l 2>/dev/null | grep "webodm-backup"
    else
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
        log "Cron scheduled: $CRON_LINE"
    fi
}

disable_cron() {
    if crontab -l 2>/dev/null | grep -q "webodm-backup"; then
        crontab -l 2>/dev/null | grep -v 'webodm-backup' | crontab -
        log "Cron removed."
    else
        log "No backup cron present."
    fi
}

run_now() {
    [[ -x "$TARGET" ]] || { log "ERROR: $TARGET not installed; run '$0 install' first"; exit 1; }
    # Run as the CURRENT user (not sudo/root): the nightly cron runs as this user, and
    # corral squashes root -> nobody, so a root run would write nobody-owned backups and
    # use a different $HOME staging dir. Keep it consistent and non-root.
    if [[ "$(id -u)" -eq 0 ]]; then
        log "WARNING: running as root -- corral writes will be squashed to 'nobody'. Prefer running as the WebODM service user."
    fi
    log "Running backup now (foreground, as $(id -un))..."
    "$TARGET"
}

status() {
    echo "== script =="
    if [[ -x "$TARGET" ]]; then ls -l "$TARGET"; else echo "NOT installed ($TARGET)"; fi
    echo "== cron =="
    crontab -l 2>/dev/null | grep "webodm-backup" || echo "no backup cron"
    echo "== last log =="
    [[ -f "$LOG_FILE" ]] && tail -n 15 "$LOG_FILE" || echo "no log at $LOG_FILE"
    echo "== alert (last failure) =="
    [[ -f "$ALERT_FILE" ]] && cat "$ALERT_FILE" || echo "none"
    echo "== stuck (D-state) processes -- backup jobs wedged on corral =="
    ps -eo stat,pid,etime,cmd | awk '$1 ~ /^D/ {print}' | grep -E 'tar|gzip|rsync|pg_dump|webodm-backup' || echo "none"
}

uninstall() {
    disable_cron
    sudo rm -f "$TARGET" "$LOGROTATE"
    log "Removed $TARGET and $LOGROTATE (log file left in place)."
}

case "${1:-}" in
    install)      install_script ;;
    enable-cron)  enable_cron ;;
    disable-cron) disable_cron ;;
    run)          run_now ;;
    status)       status ;;
    uninstall)    uninstall ;;
    *) echo "usage: $0 {install|enable-cron|disable-cron|run|status|uninstall}"; exit 1 ;;
esac
