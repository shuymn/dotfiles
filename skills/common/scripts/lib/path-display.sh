#!/usr/bin/env bash

llm_canonicalize_path() {
  local raw_path="${1-}"
  local dir_path=""
  local physical_dir=""
  local base_name=""

  if [[ -z "$raw_path" || "$raw_path" != /* ]]; then
    printf '%s' "$raw_path"
    return 0
  fi

  if [[ -d "$raw_path" ]]; then
    if physical_dir="$(cd "$raw_path" 2>/dev/null && pwd -P)"; then
      printf '%s' "$physical_dir"
      return 0
    fi
    printf '%s' "$raw_path"
    return 0
  fi

  dir_path="$(dirname "$raw_path")"
  base_name="$(basename "$raw_path")"
  if physical_dir="$(cd "$dir_path" 2>/dev/null && pwd -P)"; then
    printf '%s/%s' "$physical_dir" "$base_name"
    return 0
  fi

  printf '%s' "$raw_path"
}

llm_display_path() {
  local raw_path="${1-}"
  local physical_path=""
  local physical_pwd=""
  local base_dir=""
  local git_root=""

  if [[ -z "$raw_path" ]]; then
    printf '%s' ""
    return 0
  fi

  if [[ "$raw_path" != /* ]]; then
    printf '%s' "$raw_path"
    return 0
  fi

  physical_path="$(llm_canonicalize_path "$raw_path")"
  physical_pwd="$(pwd -P)"

  base_dir="$physical_path"
  if [[ ! -d "$base_dir" ]]; then
    base_dir="$(dirname "$physical_path")"
  fi

  if git_root="$(git -C "$base_dir" rev-parse --show-toplevel 2>/dev/null)"; then
    case "$physical_path" in
    "$git_root")
      printf '.'
      return 0
      ;;
    "$git_root"/*)
      printf '%s' "${physical_path#"$git_root"/}"
      return 0
      ;;
    esac
  fi

  case "$physical_path" in
  "$physical_pwd")
    printf '.'
    return 0
    ;;
  "$physical_pwd"/*)
    printf '%s' "${physical_path#"$physical_pwd"/}"
    return 0
    ;;
  esac

  case "$physical_path" in
  "$HOME")
    printf '~'
    return 0
    ;;
  "$HOME"/*)
    printf '~/%s' "${physical_path#"$HOME"/}"
    return 0
    ;;
  esac

  printf '%s' "$physical_path"
}
