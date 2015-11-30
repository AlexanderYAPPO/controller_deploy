#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/include/common.sh"

current_to_testing_while_current_is_on() {
    clean_mount_with_overlay_dirs $testing_partition $testing_mp
    freeze_root
    log_info "Starting copying..."
    sudo rsync -avzhP --delete "${rw_mp}/overlay/" "${testing_mp}/overlay"
    log_info "Copy is finished"
    unfreeze_root
}

current_to_testing_while_testing_is_on() {
    clean_mount_with_overlay_dirs $current_partition $current_mp
    log_info "Deleting via / files which are present in testing, but not in current..."
    sudo rm -rf `sudo diff -rq "${rw_mp}/overlay" "${current_mp}/overlay" 2>/dev/null |
      grep "^Only in ${rw_mp}/overlay" |
      sed 's/Only in //' |
      sed 's/: //'`
    log_info "Starting copying..."
    sudo rsync -avzhP "${current_mp}/overlay" /
    log_info "Copy is finished"
}

current_to_testing_while_overlayroot_is_off() {
  clean_mount_with_overlay_dirs $testing_partition $testing_mp
  clean_mount_with_overlay_dirs $current_partition $current_mp
  log_info "Starting copying..."
  sudo rsync -avzhP --delete "${current_mp}/overlay/" "${testing_mp}/overlay"
  log_info "Copy is finished"
}


log_info "You are going to copy files from current to testing."
ask_confirmation "Proceed with copying?"

check_overlayroot
overlayroot_mounted=$_RET
overlayroot_not_mounted_error=$_ERROR_MSG
overlayroot_upperdir=$_UPPER_LAYER
active_mode=$_ACTIVE_MODE

if $overlayroot_mounted; then
  log_info "Ensured that overlayroot is mounted"
  if [[ "$active_mode" == "current" ]]; then
    log_info "Ensured that \"current\" mode is on. Copying will be safe."
    current_to_testing_while_current_is_on
  elif [[ "$active_mode" == "testing" ]]; then
    log_info "\"Testing\" mode is active, testing partition is upperdir at the moment."`
             `" Files will be copied to /; overlayfs will then put them to {testing_mp}/overlay, achieving the safe copy."
    current_to_testing_while_testing_is_on
  else
    fail "Overlayroot is mounted, but the upperdir is neither testing nor current. Please check it."
  fi
else
  # TODO: test it
  log_info "Overlayroot is not mounted. Copying will be safe."
  current_to_testing_while_overlayroot_is_off
fi
