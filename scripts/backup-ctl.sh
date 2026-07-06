#!/bin/bash
# WebODM backup control -- manage the corral-safe backup WITHOUT running the full setup.sh
# (which rebuilds containers, rewrites nginx/firewall, etc.). Standalone and idempotent.
#
# Usage:
#   scripts/backup-ctl.sh install        Install/refresh /usr/local/bin/webodm-backup.sh (+ logrotate).
#                                         Does NOT schedule the cron.
#   scripts/backup-ctl.sh enable-cron    Schedule the nightly job (0 2 * * *).
#   scripts/backup-ctl.sh disable-cron   Remove the cron line.
#   scripts/backup-ctl.sh run [--db-only]  Run a backup now (foreground). --db-only skips media.
#   scripts/backup-ctl.sh status         Show install/cron/log/alert + any stuck (D-state) processes.
#   scripts/backup-ctl.sh uninstall      Remove the cron, script, and logrotate config.
#
# Design: everything heavy is built on LOCAL disk first, then moved to corral in a single
# pass -- corral is never read and written at the same time (that is what jailed the mount).
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
# do ALL heavy work on LOCAL disk, then push finished artifacts to corral in one pass.
# corral is never read+written simultaneously (that is what stacked D-state jobs before).
set -euo pipefail

# --- Config (override via environment) ---------------------------------------
MEDIA_ROOT="${WEBODM_MEDIA_ROOT:-/corral/webodm/media}"       # live media (read-only here)
BACKUP_DIR="${WEBODM_BACKUP_DIR:-/corral/webodm/backups}"     # FINAL corral destination (NOT the media tree)
MEDIA_BACKUP_DIR="$BACKUP_DIR/media"                          # corral: dated snapshots
STAGE_ROOT="${WEBODM_STAGE_ROOT:-$HOME/ODM-SUITE/backups}"    # LOCAL working area (fast disk)
DB_STAGE_DIR="$STAGE_ROOT/db"                                 # LOCAL: DB dump staging
MEDIA_MIRROR="$STAGE_ROOT/media-mirror"                       # LOCAL: persistent mirror of media
SKIP_MEDIA="${WEBODM_SKIP_MEDIA:-0}"                          # 1 = DB only (fast, for testing)

# Derive the DB name/user from WebODM's OWN config so the backup always targets the DB
# the app actually uses (defaults to WebODM's shipped webodm_dev / postgres). No drift.
WEBODM_ENV="${WEBODM_ENV_FILE:-$HOME/ODM-SUITE/WebODM/.env}"
env_val() { [[ -f "$WEBODM_ENV" ]] || return 0; grep -E "^$1=" "$WEBODM_ENV" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
DB_NAME="${WEBODM_DB:-$(env_val WO_DATABASE_NAME)}"; DB_NAME="${DB_NAME:-webodm_dev}"
DB_USER="${WEBODM_DB_USER:-$(env_val WO_DATABASE_USER)}"; DB_USER="${DB_USER:-postgres}"
LOG_FILE="${WEBODM_BACKUP_LOG:-/var/log/webodm-backup.log}"
ALERT_FILE="${WEBODM_BACKUP_ALERT:-/var/log/webodm-backup.failed}"
RETENTION_DAYS="${WEBODM_BACKUP_RETENTION_DAYS:-7}"
PREFLIGHT_TIMEOUT="${WEBODM_PREFLIGHT_TIMEOUT:-20}"           # seconds
DB_TIMEOUT="${WEBODM_DB_TIMEOUT:-1800}"                       # seconds (30m)
MEDIA_PULL_TIMEOUT="${WEBODM_MEDIA_PULL_TIMEOUT:-6h}"         # corral -> local
MEDIA_PUSH_TIMEOUT="${WEBODM_MEDIA_PUSH_TIMEOUT:-6h}"         # local  -> corral
DU_TIMEOUT="${WEBODM_DU_TIMEOUT:-15m}"                        # sizing the source

DATE=$(date +%Y%m%d_%H%M%S)

log() { printf '%s [%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$1" "${2:-}" | tee -a "$LOG_FILE" 2>/dev/null >&2 || true; }
fail() { log ERROR "$1"; date +'%Y-%m-%d %H:%M:%S' > "$ALERT_FILE" 2>/dev/null || true; echo "$1" >> "$ALERT_FILE" 2>/dev/null || true; exit 1; }

# --- Interrupt handling: kill the current child so Ctrl+C / SIGTERM stops cleanly.
CHILD=""
on_signal() { trap - INT TERM; [[ -n "$CHILD" ]] && kill "$CHILD" 2>/dev/null || true; log WARN "interrupted; stopping"; exit 130; }
trap on_signal INT TERM
# Run a command as a killable background child and wait, so signals are handled promptly
# (a foreground child wedged in NFS D-state still can't be reaped, but local phases are).
run_step() { "$@" & CHILD=$!; wait "$CHILD"; local rc=$?; CHILD=""; return $rc; }

# --- Single-instance lock (a slow/stuck run must NOT stack another) ----------
# Prefer /var/lock, fall back to /tmp so directory permissions can't block the run.
LOCK_FILE="${WEBODM_LOCK:-/var/lock/webodm-backup.lock}"
if ! exec 9>"$LOCK_FILE" 2>/dev/null; then
    LOCK_FILE="/tmp/webodm-backup.lock"
    exec 9>"$LOCK_FILE" || fail "cannot open lock file ($LOCK_FILE)"
fi
if ! flock -n 9; then
    log WARN "another backup run holds the lock; exiting without stacking"
    exit 0
fi

log INFO "backup start (DATE=$DATE, DB=$DB_NAME, skip_media=$SKIP_MEDIA, stage=$STAGE_ROOT)"

# --- Preflight: corral must be mounted, writable, and responsive -------------
# Probe corral in the BACKGROUND with a bounded wait. On a hung `hard` NFS mount even
# `timeout` cannot kill a process wedged in uninterruptible (D) I/O, so we must NOT wait
# on it: if the probe has not returned within the window, abandon it (it may remain in D
# until corral recovers) and abort -- the script/terminal is never left hanging.
corral_ok() {
    mountpoint -q /corral || { log ERROR "corral is not a mountpoint"; return 1; }
    local probe="$BACKUP_DIR/.write_test.$$"
    ( timeout "$PREFLIGHT_TIMEOUT" bash -c "mkdir -p '$BACKUP_DIR' && touch '$probe' && rm -f '$probe'" >/dev/null 2>&1 ) &
    local pp=$! waited=0 limit=$((PREFLIGHT_TIMEOUT + 5))
    while kill -0 "$pp" 2>/dev/null; do
        sleep 1; waited=$((waited + 1))
        if (( waited >= limit )); then
            log ERROR "corral did not respond in ${waited}s; mount appears hung (probe pid $pp may be stuck in D until corral recovers)"
            return 1
        fi
    done
    wait "$pp" 2>/dev/null || { log ERROR "corral not writable (probe failed within ${PREFLIGHT_TIMEOUT}s)"; return 1; }
    return 0
}
corral_ok || fail "corral preflight failed; skipping backup (mount down/hung or Permission denied)"
mkdir -p "$STAGE_ROOT" "$DB_STAGE_DIR" || fail "cannot create local staging under $STAGE_ROOT"

# --- Database backup: dump LOCALLY, verify, then copy to corral in one pass ---
db_ok=false
if docker ps --format '{{.Names}}' | grep -qx db; then
    stage="$DB_STAGE_DIR/${DB_NAME}_$DATE.dump"
    if timeout "$DB_TIMEOUT" docker exec db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$stage"; then
        # Structural integrity check (TOC readable) -- not a full restore drill.
        if [[ -s "$stage" ]] && docker exec -i db pg_restore --list < "$stage" >/dev/null 2>&1; then
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
    timeout 5m find "$DB_STAGE_DIR" -type f -name '*.dump' -mtime "+$RETENTION_DAYS" -delete || log WARN "local staging prune timed out"
else
    fail "db container not running; cannot back up database"
fi

# --- Media backup: LOCAL mirror first, then push a snapshot to corral --------
# Phase 1 reads corral -> writes LOCAL (interruptible). Phase 2 reads LOCAL -> writes
# corral, --link-dest against the previous corral snapshot so only deltas are written.
# corral is never read and written at the same time.
media_ok=false
if [[ "$SKIP_MEDIA" == "1" ]]; then
    log INFO "media backup skipped (WEBODM_SKIP_MEDIA=1)"
elif [[ -d "$MEDIA_ROOT" ]]; then
    mkdir -p "$MEDIA_MIRROR" "$MEDIA_BACKUP_DIR"

    # Free-space guard: local disk must hold a full mirror. Account for what the mirror
    # already occupies (incremental runs need little extra). Abort loudly rather than
    # fill the disk (which would be a new incident).
    avail_kb=$(df -Pk "$MEDIA_MIRROR" 2>/dev/null | awk 'NR==2{print $4}')
    mirror_kb=$(du -sk "$MEDIA_MIRROR" 2>/dev/null | awk '{print $1}'); mirror_kb=${mirror_kb:-0}
    need_kb=$(timeout "$DU_TIMEOUT" ionice -c3 nice -n19 du -sk "$MEDIA_ROOT" 2>/dev/null | awk '{print $1}')
    if [[ -n "${need_kb:-}" && -n "${avail_kb:-}" ]]; then
        # usable = free space + space we can reuse from the existing mirror
        if (( avail_kb + mirror_kb < need_kb + need_kb/10 )); then
            fail "insufficient local space at $MEDIA_MIRROR: source ~$((need_kb/1024))MB, usable ~$(((avail_kb+mirror_kb)/1024))MB. Set WEBODM_STAGE_ROOT to a bigger disk or use WEBODM_SKIP_MEDIA=1."
        fi
        log INFO "local space ok (source ~$((need_kb/1024))MB, usable ~$(((avail_kb+mirror_kb)/1024))MB)"
    else
        log WARN "could not size $MEDIA_ROOT within $DU_TIMEOUT; proceeding (rsync fails loud on ENOSPC)"
    fi

    # Phase 1: corral -> local mirror (incremental; throttled; time-boxed).
    if run_step timeout "$MEDIA_PULL_TIMEOUT" ionice -c3 nice -n19 \
         rsync -a --delete --partial "$MEDIA_ROOT/" "$MEDIA_MIRROR/"; then
        log INFO "local mirror updated: $MEDIA_MIRROR"
    else
        fail "media pull (corral -> local) failed or timed out (${MEDIA_PULL_TIMEOUT})"
    fi

    # Phase 2: local mirror -> corral dated snapshot (hardlink unchanged vs previous).
    snap_dir="$MEDIA_BACKUP_DIR/$DATE"
    latest_link="$MEDIA_BACKUP_DIR/latest"
    link_dest=()
    [[ -d "$latest_link" ]] && link_dest=(--link-dest="$latest_link")
    if run_step timeout "$MEDIA_PUSH_TIMEOUT" ionice -c3 nice -n19 \
         rsync -a --partial "${link_dest[@]}" "$MEDIA_MIRROR/" "$snap_dir/"; then
        ln -sfn "$snap_dir" "$latest_link.tmp" && mv -Tf "$latest_link.tmp" "$latest_link"
        log INFO "media snapshot pushed to corral: $snap_dir"
        media_ok=true
    else
        fail "media push (local -> corral) failed or timed out (${MEDIA_PUSH_TIMEOUT})"
    fi
else
    log WARN "media root $MEDIA_ROOT not found; skipping media backup"
fi

# --- Retention (time-boxed) --------------------------------------------------
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
    # corral squashes root -> nobody, so a root run would write nobody-owned backups.
    if [[ "$(id -u)" -eq 0 ]]; then
        log "WARNING: running as root -- corral writes will be squashed to 'nobody'. Prefer the WebODM service user."
    fi
    local skip=0
    [[ "${1:-}" == "--db-only" ]] && skip=1
    log "Running backup now (foreground, as $(id -un)${skip:+, db-only=$skip})..."
    WEBODM_SKIP_MEDIA="$skip" "$TARGET"
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
    run)          run_now "${2:-}" ;;
    status)       status ;;
    uninstall)    uninstall ;;
    *) echo "usage: $0 {install|enable-cron|disable-cron|run [--db-only]|status|uninstall}"; exit 1 ;;
esac
