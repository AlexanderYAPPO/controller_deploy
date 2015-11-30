#!/bin/bash

set -e

root_partition=/dev/sda1
testing_partition=/dev/sdb1
current_partition=/dev/sdc1

ro_mp=/media/root-ro
rw_mp=/media/root-rw

current_mp=/media/current
testing_mp=/media/testing

curr_dir="$(dirname "$BASH_SOURCE")"
project_root="`dirname "$curr_dir"`"

log() {
  echo "$@"
}
log_info() {
  log "INFO: $@"
}

error() {
    printf "ERROR: $@\n" 1>&2
}
fail() { [ $# -eq 0 ] || error "$@"; exit 1; }

# args: overlayfs info from mount command, name of dir to validate, correct value and error message
validate_dir() {
  local overlay_str=$1 dirname=$2 correct_mp=$(readlink -m "$3") error_msg=$4
  local dir_str=${overlay_str##*,${dirname}=} # trim overlay_str up to $dirname=
  local parsed_dir=${dir_str%%,*} # trim dir_str from the first ',' to the end
  parsed_dir=$(readlink -m "$parsed_dir")
  if [[ "${parsed_dir}" != "$correct_mp" ]]; then
    _RET=false
    _ERROR_MSG=$error_msg
    _ACTIVE_MODE="off"
  fi
}

# check that overlayfs is active and mounted in correct places
check_overlayroot() {
  _RET=true
  _ERROR_MSG=
  _UPPER_LAYER=
  _ACTIVE_MODE=
  overlay_str=$(grep -m1 "^overlayroot / overlayfs " /proc/mounts) || true
  if [ -n "${overlay_str}" ]; then
    validate_dir "$overlay_str" "lowerdir" "${ro_mp}" "Overlayfs is found, but lowerdir mount point is not ${ro_mp}, seems like this is not overlayroot"
    validate_dir "$overlay_str" "upperdir" "${rw_mp}/overlay" "Overlayfs is found, but upperdir mount point is not ${rw_mp}/overlay, seems like this is not overlayroot"
    if $_RET; then
      get_dev_by_mp "$rw_mp"
      _UPPER_LAYER=$_RET
      if [[ "$_UPPER_LAYER" == "$current_partition" ]]; then
        _ACTIVE_MODE="current"
      elif [[ "$_UPPER_LAYER" == "$testing_partition" ]]; then
        _ACTIVE_MODE="testing"
      fi
      _RET=true
    fi
  else
    _RET=false
    _ERROR_MSG="unable to find overlayroot filesystem"
    _ACTIVE_MODE="off"
  fi
}

# get device name by mountpoint
# accepts one argument -- the mountpoint
get_dev_by_mp() {
  _RET=
  dev_string=$(grep -m1 "^.* $1 .*" /proc/mounts)
  _RET=${dev_string%% *}
}

# args: what and where
clean_mount() {
  local dev_name=$1 mp=$2
  sudo umount $dev_name &>/dev/null || true
  sudo mkdir -p $mp
  sudo mount $dev_name $mp
}
# args: what and where
clean_mount_with_overlay_dirs() {
  local dev_name=$1 mp=$2
  clean_mount $dev_name $mp
  sudo mkdir -p "${mp}/overlay" "${mp}/overlay-workdir"
}

freeze_root() {
  sudo mount -o remount,ro / && log_info "Root is freezed"
}
unfreeze_root() {
  sudo mount -o remount,rw / && log_info "Root is unfreezed"
}

# remove all files and dirs inside $1
clean_out_dir() {
  sudo find $1 -mindepth 1 -delete
}

ask_confirmation() {
  read -p "$1 y/n" -n 1 -r
  echo
  if ! [[ $REPLY =~ ^[Yy]$ ]]; then
    exit 0
  fi
}

ask_boolean() {
  _RET=
  read -p "$1 y/n" -n 1 -r
  echo
  if ! [[ $REPLY =~ ^[Yy]$ ]]; then
    _RET=true
  else
    _RET=false
  fi
}

# the only argument is the reason
get_reboot_recommendation_string () {
  local reason=$1
  _RES="Since overlayfs rules has been violated by"
  _RES="$_RES $reason"
  _RES="$_RES, it is highly recommended to reboot now immediately. You will be prompted to change the mode."
}
