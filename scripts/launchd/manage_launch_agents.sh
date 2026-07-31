#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${PROJECT_ROOT}/scripts/launchd/common.sh"
ensure_runtime_dirs

TPL_ROOT="${PROJECT_ROOT}/scripts/launchd/plists"
GEN_ROOT="${PROJECT_ROOT}/runtime/agent_orchestrator/launchd/plists"
USER_AGENT_ROOT="${HOME}/Library/LaunchAgents"
SYSTEM_DAEMON_ROOT="/Library/LaunchDaemons"

LAUNCH_PATH="${LAUNCH_PATH:-/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"

LABELS=(
  "com.bettingpool.main"
  "com.bettingpool.orchestrator.planner"
  "com.bettingpool.orchestrator.worker"
  "com.bettingpool.orchestrator.worker-daemon"
  "com.bettingpool.orchestrator.copilot-daemon"
)

resolve_target_user() {
    if [[ -n "${BETTINGPOOL_TARGET_USER:-}" ]]; then
        printf "%s\n" "${BETTINGPOOL_TARGET_USER}"
        return
    fi
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        printf "%s\n" "${SUDO_USER}"
        return
    fi
    stat -f "%Su" /dev/console 2>/dev/null || id -un
}

resolve_user_home() {
    local user_name="${1}"
    dscl . -read "/Users/${user_name}" NFSHomeDirectory 2>/dev/null | awk '{print $2}'
}

validate_scope() {
    local scope="${1}"
    if [[ "${scope}" != "user" && "${scope}" != "system" ]]; then
        log_error "Unsupported scope: ${scope} (expected user or system)"
        exit 1
    fi
}

require_root_for_system_scope() {
    local scope="${1}"
    local command_name="${2}"
    if [[ "${scope}" == "system" && "${command_name}" =~ ^(install|reload|unload|remove)$ && "${EUID}" -ne 0 ]]; then
        log_error "System scope requires sudo/root. Example: sudo bash scripts/launchd/manage_launch_agents.sh install --scope system"
        exit 1
    fi
}

scope_domain() {
    local scope="${1}"
    local target_user="${2}"
    if [[ "${scope}" == "system" ]]; then
        printf "system\n"
        return
    fi
    local target_uid
    target_uid="$(id -u "${target_user}")"
    printf "gui/%s\n" "${target_uid}"
}

scope_install_root() {
    local scope="${1}"
    local target_user="${2}"
    if [[ "${scope}" == "system" ]]; then
        printf "%s\n" "${SYSTEM_DAEMON_ROOT}"
        return
    fi
    local target_home
    target_home="$(resolve_user_home "${target_user}")"
    printf "%s/Library/LaunchAgents\n" "${target_home}"
}

template_to_label() {
    local template="${1}"
    basename "${template}" | sed 's/\.plist\.tmpl$//'
}

render_template() {
    local template="${1}"
    local output="${2}"
    local scope="${3}"
    local run_as_user="${4}"
    local user_home
    user_home="$(resolve_user_home "${run_as_user}")"
    sed \
      -e "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
      -e "s|__LAUNCH_PATH__|${LAUNCH_PATH}|g" \
      -e "s|__USER_HOME__|${user_home}|g" \
      "${template}" > "${output}"

    if [[ "${scope}" == "system" ]]; then
        perl -0pi -e 's|(<key>Label</key>\s*<string>[^<]+</string>)|$1\n\n    <key>UserName</key>\n    <string>'"${run_as_user}"'</string>|' "${output}"
    fi
}

render_all() {
    local scope="${1}"
    local run_as_user="${2}"
    mkdir -p "${GEN_ROOT}"
    for tmpl in "${TPL_ROOT}"/*.plist.tmpl; do
        local label
        label="$(template_to_label "${tmpl}")"
        local out="${GEN_ROOT}/${label}.plist"
        render_template "${tmpl}" "${out}" "${scope}" "${run_as_user}"
    done
    log_info "Rendered ${scope} plists to ${GEN_ROOT}"
}

install_all() {
    local scope="${1}"
    local install_root="${2}"
    local domain="${3}"
    local run_as_user="${4}"
    render_all "${scope}" "${run_as_user}"
    mkdir -p "${install_root}"
    for label in "${LABELS[@]}"; do
        local src="${GEN_ROOT}/${label}.plist"
        local dst="${install_root}/${label}.plist"
        cp "${src}" "${dst}"
        if [[ "${scope}" == "system" ]]; then
            chown root:wheel "${dst}"
            chmod 644 "${dst}"
            launchctl bootout "${domain}" "${dst}" >/dev/null 2>&1 || true
            launchctl bootstrap "${domain}" "${dst}"
            launchctl enable "${domain}/${label}" >/dev/null 2>&1 || true
        else
            launchctl unload "${dst}" >/dev/null 2>&1 || true
            launchctl load -w "${dst}"
        fi
        log_info "Installed and bootstrapped ${label} (${scope})"
    done
}

unload_all() {
    local scope="${1}"
    local install_root="${2}"
    local domain="${3}"
    for label in "${LABELS[@]}"; do
        local dst="${install_root}/${label}.plist"
        if [[ "${scope}" == "system" ]]; then
            launchctl bootout "${domain}" "${dst}" >/dev/null 2>&1 || true
            launchctl disable "${domain}/${label}" >/dev/null 2>&1 || true
        else
            launchctl unload -w "${dst}" >/dev/null 2>&1 || true
        fi
        log_info "Unloaded ${label} (${scope})"
    done
}

remove_all() {
    local scope="${1}"
    local install_root="${2}"
    local domain="${3}"
    unload_all "${scope}" "${install_root}" "${domain}"
    for label in "${LABELS[@]}"; do
        rm -f "${install_root}/${label}.plist"
        log_info "Removed ${install_root}/${label}.plist"
    done
}

status_all() {
    local scope="${1}"
    local domain="${2}"
    for label in "${LABELS[@]}"; do
        if launchctl print "${domain}/${label}" >/dev/null 2>&1; then
            local state
            local last_exit
            state="$(launchctl print "${domain}/${label}" | awk -F'= ' '/state = / {print $2; exit}')"
            last_exit="$(launchctl print "${domain}/${label}" | awk -F'= ' '/last exit code = / {print $2; exit}')"
            echo "${label}: LOADED (${scope}, state=${state:-unknown}, last_exit=${last_exit:-n/a})"
        else
            echo "${label}: NOT_LOADED (${scope})"
        fi
    done

    local python_bin="${PROJECT_ROOT}/.venv/bin/python"
    if [[ -x "${python_bin}" ]]; then
        echo
        echo "execution_policy:"
        "${python_bin}" - <<'PY'
from orchestrator import db, execution_policy

db.init_db()
state = execution_policy.get_state()
print(
    "  mode={mode} scheduler={scheduler} cto={cto} blocked={blocked} active={active}".format(
        mode=state["llm_execution_mode"],
        scheduler=state["scheduler_enabled"],
        cto=state["cto_scheduler_enabled"],
        blocked=state["llm_blocked_count"],
        active=state["active_background_runner"] or "-",
    )
)
print(
    "  last_call={call} runner={runner} provider={provider}".format(
        call=state["last_llm_call_at"] or "-",
        runner=state["last_llm_call_runner"] or "-",
        provider=state["last_llm_call_provider"] or "-",
    )
)
print(
    "  last_blocked={blocked_at} reason={reason}".format(
        blocked_at=state["last_llm_blocked_at"] or "-",
        reason=state["last_llm_blocked_reason"] or "-",
    )
)
for runner in ("planner_tick", "worker_tick", "cto_review_tick"):
    latest = db.get_latest_run_by_runner(runner)
    if latest:
        print(
            "  {runner}: {outcome} at {tick} :: {message}".format(
                runner=runner,
                outcome=latest.get("outcome") or "-",
                tick=latest.get("tick_at") or "-",
                message=(latest.get("message") or "-")[:120],
            )
        )
PY
    fi
}

print_help() {
    cat <<'EOF'
Usage: scripts/launchd/manage_launch_agents.sh <command>

Commands:
  render      Render template plists into runtime/agent_orchestrator/launchd/plists
    install     Render + install into launchd for the selected scope
    reload      Re-render + bootout/bootstrap for the selected scope
    unload      launchctl bootout for all bettingpool labels in the selected scope
    remove      unload + remove plist files from the selected scope
    status      Show launchd state for all labels in the selected scope
  logs        Tail core launchd logs

Options:
    --scope user|system   user=LaunchAgent after login; system=LaunchDaemon before login (requires sudo)
EOF
}

tail_logs() {
    tail -n 120 -f \
      "${LAUNCHD_LOG_ROOT}/main_agent.out.log" \
      "${LAUNCHD_LOG_ROOT}/main_agent.err.log" \
      "${LAUNCHD_LOG_ROOT}/planner_tick.out.log" \
      "${LAUNCHD_LOG_ROOT}/worker_tick.out.log" \
      "${LAUNCHD_LOG_ROOT}/worker_daemon.out.log"
}

cmd="help"
scope="${BETTINGPOOL_LAUNCH_SCOPE:-user}"

while [[ $# -gt 0 ]]; do
    case "${1}" in
        render|install|reload|unload|remove|status|logs|help|-h|--help)
            cmd="${1}"
            shift
            ;;
        --scope)
            scope="${2:-}"
            shift 2
            ;;
        *)
            log_error "Unknown argument: ${1}"
            print_help
            exit 1
            ;;
    esac
done

validate_scope "${scope}"
require_root_for_system_scope "${scope}" "${cmd}"

target_user="$(resolve_target_user)"
install_root="$(scope_install_root "${scope}" "${target_user}")"
domain="$(scope_domain "${scope}" "${target_user}")"

case "${cmd}" in
    render) render_all "${scope}" "${target_user}" ;;
    install) install_all "${scope}" "${install_root}" "${domain}" "${target_user}" ;;
    reload)
        unload_all "${scope}" "${install_root}" "${domain}"
        install_all "${scope}" "${install_root}" "${domain}" "${target_user}"
        ;;
    unload) unload_all "${scope}" "${install_root}" "${domain}" ;;
    remove) remove_all "${scope}" "${install_root}" "${domain}" ;;
    status) status_all "${scope}" "${domain}" ;;
    logs) tail_logs ;;
    help|-h|--help) print_help ;;
    *)
        print_help
        exit 1
        ;;
esac
