#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/common.sh"
source "${project_root}/include/change_mode_logic.sh"

# args: active mode and partition to remove
rm_partition(){
  local active_mode="$1" partition_to_remove="$2"
  if [[ "$partition_to_remove" == "$active_mode" ]]; then
    rm_partition_online "$active_mode"
  elif [[ "$partition_to_remove" == "current" ]]; then
    rm_partition_offline "$current_partition" "$current_mp" "$partition_to_remove"
  elif [[ "$partition_to_remove" == "testing" ]]; then
    rm_partition_offline "$testing_partition" "$testing_mp" "$partition_to_remove"
  else
    show_clean_partition_usage
  fi
}

rm_partition_online(){
  local mode=$1
  ask_confirmation "You are asking to clean ${mode} partition which is active now."`
                     `" It is a violation of overlayfs rules. Proceed anyway?"
  clean_out_dir ${rw_mp}
  get_reboot_recommendation_string "removing ${mode} files from ${mode} mode"
  log_info "$_RES"
  change_mode_prompt_destination "${mode}"
}

rm_partition_offline(){
  local partition=$1 mp=$2 partition_mode=$3
  ask_confirmation "You are asking to clean ${partition_mode} partition. The deletion will be safe. Proceed?"
  clean_mount_with_overlay_dirs "$partition" "$mp"
  clean_out_dir "$mp"
}

show_clean_partition_usage(){
  log_info "Usage: change_mode.sh <current | testing>"
}