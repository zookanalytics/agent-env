#!/usr/bin/env bash
# agent-env bash completion script
# Install: eval "$(agent-env completion bash)"

_agent_env_repos() {
  local ws_dir=~/.agent-env/workspaces
  local entry base repo
  if [[ -d "${ws_dir}" ]]; then
    for entry in "${ws_dir}"/*/; do
      [[ -d "${entry}" ]] || continue
      base="${entry%/}"
      base="${base##*/}"
      repo="${base%-*}"
      [[ "${repo}" != "${base}" ]] && echo "${repo}"
    done | sort -u
  fi
}

_agent_env_instances() {
  local ws_dir=~/.agent-env/workspaces
  local entry base
  if [[ -d "${ws_dir}" ]]; then
    for entry in "${ws_dir}"/*/; do
      [[ -d "${entry}" ]] || continue
      base="${entry%/}"
      base="${base##*/}"
      echo "${base}"
    done | sort -u
  fi
}

_agent_env_completions() {
  local cur prev commands
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  commands="create env list ps attach path code rebuild shutdown remove purpose on repos tmux-status completion"

  # Complete commands at position 1
  if [[ ${COMP_CWORD} -eq 1 ]]; then
    COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
    return 0
  fi

  # Complete based on command
  case "${prev}" in
    on|code|attach|path|purpose)
      local instances
      instances="$(_agent_env_instances)"
      COMPREPLY=($(compgen -W "--repo ${instances}" -- "${cur}"))
      return 0
      ;;
    create)
      COMPREPLY=($(compgen -W "--repo --purpose --attach" -- "${cur}"))
      return 0
      ;;
    list|ps)
      COMPREPLY=($(compgen -W "--json --repo" -- "${cur}"))
      return 0
      ;;
    rebuild)
      local instances
      instances="$(_agent_env_instances)"
      COMPREPLY=($(compgen -W "--force --yes --no-pull --use-cache --repo ${instances}" -- "${cur}"))
      return 0
      ;;
    shutdown)
      local instances
      instances="$(_agent_env_instances)"
      COMPREPLY=($(compgen -W "--yes --repo ${instances}" -- "${cur}"))
      return 0
      ;;
    remove)
      local instances
      instances="$(_agent_env_instances)"
      COMPREPLY=($(compgen -W "--force --repo ${instances}" -- "${cur}"))
      return 0
      ;;
    repos)
      COMPREPLY=($(compgen -W "--json" -- "${cur}"))
      return 0
      ;;
    tmux-status)
      # no arguments or options
      return 0
      ;;
    completion)
      COMPREPLY=($(compgen -W "bash zsh" -- "${cur}"))
      return 0
      ;;
    --repo)
      COMPREPLY=($(compgen -W "$(_agent_env_repos)" -- "${cur}"))
      return 0
      ;;
  esac

  return 0
}

complete -F _agent_env_completions agent-env

# aecd: cd into an instance's host directory
aecd() {
  local dir
  dir="$(agent-env path "$@")" || return 1
  cd "${dir}" || return 1
}

_aecd_completions() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  local prev="${COMP_WORDS[COMP_CWORD-1]}"
  local i has_repo=0
  for ((i=1; i < COMP_CWORD; i++)); do
    [[ "${COMP_WORDS[i]}" == "--repo" ]] && has_repo=1 && break
  done
  if [[ "${prev}" == "--repo" ]]; then
    COMPREPLY=($(compgen -W "$(_agent_env_repos)" -- "${cur}"))
  elif [[ "${cur}" == -* && ${has_repo} -eq 0 ]]; then
    COMPREPLY=($(compgen -W "--repo" -- "${cur}"))
  else
    COMPREPLY=($(compgen -W "$(_agent_env_instances)" -- "${cur}"))
  fi
}

complete -F _aecd_completions aecd
