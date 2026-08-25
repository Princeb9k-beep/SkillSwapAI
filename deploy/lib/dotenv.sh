# deploy/lib/dotenv.sh — THE dotenv parser. Source it; do not copy it.
#
#     . "$SCRIPT_DIR/lib/dotenv.sh"
#     value="$(skillswap_dotenv_value /path/to/.env SOME_KEY)"   # rc 1 if absent
#
# ── WHY THIS IS NOT `source .env` ──────────────────────────────────────────
# `source` does NOT glue an inline comment onto a value and does NOT keep a
# trailing tab — the shell's own word-splitting handles both. What it actually
# does, on `SPACED=two words here`:
#
#     .env: line 7: words: command not found
#
# The variable is left UNSET and the remainder of the line is EXECUTED. That is
# the reason: reading a value must not run the file. Any unquoted value with a
# space is a command, and `.env` holds secrets, not code.
#
# Once you are grepping the line yourself rather than letting the shell parse
# it, the comment/quote/trim handling the shell would have done becomes yours
# to do — and getting it wrong is a real incident. In the sibling Nova Flow
# deployment, `POSTGRES_USER=nova_user   # app role` reached pgbouncer with
# " # app role" glued on and every authentication failed with "no such user".
#
# The semantics below match Docker Compose's own parser, which is the thing
# that has to agree with us:
#
#   * the LAST assignment of a key wins
#   * `export KEY=…` is an assignment of KEY
#   * a double- or single-quoted value is returned verbatim, inner `#` included
#   * an unquoted value is cut at a whitespace-preceded `#`, then right-trimmed
#     of ALL trailing whitespace — spaces, TABS, and a CRLF file's \r
#
# The tab case is not hypothetical: a copy of this function elsewhere had its
# right-trim degrade to `while [ "${v% }" != "$v" ]`, which strips literal
# SPACES only, and a tab-terminated hostname reached ssh-keyscan intact and was
# rejected as "hostname contains invalid characters".
#
# ── POSIX ON PURPOSE ───────────────────────────────────────────────────────
# `case`, not `[[ ]]`, and no bashisms: this file is sourced from contexts that
# are not guaranteed to be bash. A bashism here is a job that dies at 03:00
# with a syntax error.
#
# This function is byte-for-byte the canonical parser used by the Nova Flow
# deployment (APP_LLM `deploy/lib/dotenv.sh`, between its canonical markers)
# with only the name prefix changed. Keep it that way — the two deployments
# share a `.env` shape and an operator, and a parser that disagrees with the
# other one is worse than no parser.

# ── canonical:begin ────────────────────────────────────────────────────────
# skillswap_dotenv_value <file> <KEY> → value on stdout.
# Returns 1 when the key is ABSENT (distinct from present-but-empty, which
# returns 0 and prints nothing). Callers that do not care say `|| true` —
# and MUST, because an unguarded `v=$(...)` carries the rc and aborts the
# script under `set -e`.
skillswap_dotenv_value() {
    local _f="$1" _k="$2" _v
    _v="$(grep -E "^(export[[:space:]]+)?${_k}=" "$_f" 2>/dev/null | tail -1 || true)"
    [ -n "$_v" ] || return 1
    _v="${_v#*=}"
    case "$_v" in
        \"*)  _v="${_v#\"}"; _v="${_v%%\"*}" ;;      # "quoted" — verbatim
        \'*)  _v="${_v#\'}"; _v="${_v%%\'*}" ;;      # 'quoted' — verbatim
        *)    _v="${_v%%[[:space:]]\#*}"             # bare — cut inline comment
              while [ -n "$_v" ]; do                 # …then right-trim ALL
                  case "$_v" in                      # trailing whitespace
                      *[[:space:]]) _v="${_v%?}" ;;
                      *) break ;;
                  esac
              done ;;
    esac
    printf '%s' "$_v"
}
# ── canonical:end ──────────────────────────────────────────────────────────
