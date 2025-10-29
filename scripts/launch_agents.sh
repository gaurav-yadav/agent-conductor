#!/usr/bin/env bash
#
# Launch a conductor supervisor plus developer, tester, and reviewer workers
# in a shared Agent Conductor session. Assumes the API server is already running.

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv CLI is required (https://docs.astral.sh/uv/)." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required to parse command output." >&2
  exit 1
fi

provider="${AC_PROVIDER:-claude_code}"
conductor_profile="${AC_CONDUCTOR_PROFILE:-conductor}"
developer_profile="${AC_DEVELOPER_PROFILE:-developer}"
tester_profile="${AC_TESTER_PROFILE:-tester}"
reviewer_profile="${AC_REVIEWER_PROFILE:-reviewer}"
# Optional kickoff instruction automatically sent to the conductor when non-empty.
# Edit this value (or export AC_INITIAL_INSTRUCTION before running) to auto-seed the session.
initial_message="${AC_INITIAL_INSTRUCTION:-Please run an end-to-end coordination: instruct the developer to update agent-conductor/test-workspace/add.js so the add function doubles its input, confirm completion, then have the tester write and run checks to prove the behavior, and finally ask the reviewer to sign off on the change with a summary, communicate only via messages.}"

echo "Launching conductor supervisor (provider: ${provider}, profile: ${conductor_profile})..."
conductor_json="$(uv run agent-conductor launch \
  --provider "${provider}" \
  --agent-profile "${conductor_profile}" \
  --role supervisor
)"

session_name="$(echo "${conductor_json}" | jq -r '.session_name')"
conductor_id="$(echo "${conductor_json}" | jq -r '.id')"

if [[ -z "${session_name}" || "${session_name}" == "null" ]]; then
  echo "Failed to obtain session name from launch response:" >&2
  echo "${conductor_json}" >&2
  exit 1
fi

echo "Session '${session_name}' created. Conductor terminal ID: ${conductor_id}"

declare -a worker_roles=("developer" "tester" "reviewer")
declare -a worker_profiles=("${developer_profile}" "${tester_profile}" "${reviewer_profile}")
declare -a worker_ids=()

for idx in "${!worker_roles[@]}"; do
  role="${worker_roles[$idx]}"
  profile="${worker_profiles[$idx]}"
  echo "Launching ${role} worker (profile: ${profile})..."
  worker_json="$(uv run agent-conductor worker "${session_name}" \
    --provider "${provider}" \
    --agent-profile "${profile}" \
    --role "${role}"
  )"
  worker_id="$(echo "${worker_json}" | jq -r '.id')"

  if [[ -z "${worker_id}" || "${worker_id}" == "null" ]]; then
    echo "Failed to obtain terminal ID for ${role} worker:" >&2
    echo "${worker_json}" >&2
    exit 1
  fi

  worker_ids+=("${role}:${worker_id}")
  echo "  ${role} terminal ID: ${worker_id}"
done

echo
echo "Launch complete."
echo "  Session name: ${session_name}"
echo "  Conductor terminal ID: ${conductor_id}"
for entry in "${worker_ids[@]}"; do
  role="${entry%%:*}"
  id="${entry#*:}"
  first_letter="$(printf '%s' "${role:0:1}" | tr '[:lower:]' '[:upper:]')"
  echo "  ${first_letter}${role:1} terminal ID: ${id}"
done

echo

if [[ -n "${initial_message}" ]]; then
  echo "Dispatching initial instruction to conductor..."
  uv run agent-conductor send "${conductor_id}" --message "${initial_message}"
  echo "Initial instruction sent."
  echo
fi

echo "Use 'uv run agent-conductor send <terminal-id> --message \"...\"' to communicate with each terminal."
