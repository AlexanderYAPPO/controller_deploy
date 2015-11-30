#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/include/common.sh"
source "${project_root}/include/clean_partition_logic.sh"
source "${project_root}/include/change_mode_logic.sh"

overlay_warning() {
 active_mode=$1
 log_info "Overlayroot is on, $active_mode mode is active now. You are going to copy files to the lower (root) layer. "`
          `" This action violates overlayfs rules. The recommended way is to reboot in overlay-free"`
          `" (change_mode.sh off) mode and perform the copy there."
 ask_confirmation "Proceed with copying anyway?"
}

overlay_post_copy() {
 get_reboot_recommendation_string "copying files to lowerdir"
 log_info "$_RES"
 change_mode_prompt_destination $active_mode
}

testing_to_stable_while_current_is_on(){
  clean_mount_with_overlay_dirs $testing_partition $testing_mp
  freeze_root
  sudo mount -o remount,rw "${ro_mp}" && log_info "lowerdir is remounted as rw" || fail "Unable to remount [$ro_mp] writable"
  log_info "Starting copying..."
  sudo rsync -avzhP "${testing_mp}/overlay" "${ro_mp}"
  log_info "Copy is finished"
  mount -o remount,ro "${ro_mp}" && log_info "lowerdir is remounted as ro" || error "Note that [$ro_mp] is still writable"
  unfreeze_root
  ask_boolean "Do you want to clean testing partition now? It is safe."
  rm_testing=$_RET
  if $rm_testing; then
    rm_testing_offline
  fi
  overlay_post_copy
}

testing_to_stable_while_testing_is_on(){
  freeze_root
  sudo mount -o remount,rw "${ro_mp}" && log_info "lowerdir is remounted as rw" || fail "Unable to remount [$ro_mp] writable"
  log_info "Starting copying..."
  sudo rsync -avzhP "${rw_mp}/overlay" "${ro_mp}"
  log_info "Copy is finished"
  sudo mount -o remount,ro "${ro_mp}" && log_info "lowerdir is remounted as ro" || error "Note that [$ro_mp] is still writable"
  unfreeze_root
  ask_boolean "Do you want to clean testing partition now? This is also a violation of overlayfs rules."
  rm_testing=$_RET
  if $rm_testing; then
    rm_partition "$active_mode" "testing"
  fi
  overlay_post_copy
}

testing_to_stable_while_overlayroot_is_off(){
  clean_mount_with_overlay_dirs $testing_partition $testing_mp
  log_info "Starting copying..."
  sudo rsync -avzhP "${testing_mp}/overlay" /
  log_info "Copy is finished"
  ask_boolean "Do you want to clean testing partition now? It is safe."
  rm_testing=$_RET
  if $rm_testing; then
    rm_partition "$active_mode" "testing"
  fi
}

check_overlayroot
overlayroot_mounted=$_RET
overlayroot_not_mounted_error=$_ERROR_MSG
overlayroot_upperdir=$_UPPER_LAYER
active_mode=$_ACTIVE_MODE

if $overlayroot_mounted; then
  log_info "Ensured that overlayroot is mounted"
  if [[ "$active_mode" == "current" ]]; then
    log_info "Ensured that \"current\" mode is on"
    overlay_warning "current"
    testing_to_stable_while_current_is_on
  elif [[ "$active_mode" == "testing" ]]; then
    log_info "Ensured that \"testing\" mode is on"
    overlay_warning "testing"
    testing_to_stable_while_testing_is_on
  else
    fail "Overlayroot is mounted, but the upperdir is neither testing nor current. Please check it."
  fi
else
  log_info "Overlayroot is not mounted. Copying will be safe."
  testing_to_stable_while_overlayroot_is_off
fi
