#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/common.sh"

local_cfg_path="${project_root}/conf/overlayroot.conf"

# the only argument is active mode
change_mode_prompt_destination(){
  local active_mode=$1
  log_info "Active mode is $active_mode. Please enter the mode to switch. Leave the field empty, if you want to keep it and just reboot."
  read dest_mode
  change_mode $active_mode $dest_mode
}

# args: active mode and optional destination mode
change_mode(){
  local active_mode=$1
  if [ "$#" -eq 1 ]; then
    ask_confirmation "You've left the destination mode field empty. The $active_mode mode will be kept. Reboot now?"
  else
    local destination_mode=$2
    if [[ "$active_mode" == "$destination_mode" ]]; then
      ask_confirmation "You've entered the $active_mode which is active now. The mode will be kept. Reboot now?"
    else
      get_config_line $destination_mode
      ask_confirmation "You've entered the ${destination_mode} mode as the mode to switch. Change config and reboot now?"
      if [[ "$active_mode" == "off" ]]; then
        change_config "/etc/overlayroot.conf" "${_RET}"
      else
        change_config_from_overlay "${_RET}"
      fi
    fi
  fi
  change_mode_reboot
}

change_config_from_overlay(){
  freeze_root
  sudo mount -o remount,rw "${ro_mp}" && log_info "lowerdir is remounted as rw" || fail "Unable to remount [$ro_mp] writable"
  if [ "$#" -eq 1 ]; then
    change_config "${ro_mp}/etc/overlayroot.conf" "$1"
  else
    change_config "${ro_mp}/etc/overlayroot.conf"
  fi
}

# args: location of overlayroot config and [line to add]
change_config(){
  local cfg_dest_path="$1" # /etc/overlayroot.conf or /media/root-ro/etc/overlayroot.conf
  sudo cp "${local_cfg_path}" "${cfg_dest_path}"
  if [ "$#" -eq 2 ]; then
    local line_to_add="$2"
    sudo bash -c "echo '${line_to_add}' >> ${cfg_dest_path}"
  fi
}

change_mode_reboot(){
  reboot_delay=2
  log_info "Rebooting in $reboot_delay seconds..."
  sleep $reboot_delay
  sudo reboot
}

# the only argument is the mode
get_config_line(){
  _RET=
  local mode=$1
  if [[ "$mode" == "current" ]]; then
    _RET="overlayroot=device:dev=${current_partition},timeout=60 # current"
  elif [[ "$mode" == "testing" ]]; then
    _RET="overlayroot=device:dev=${testing_partition},timeout=60 # testing"
  elif [[ "$mode" == "off" ]]; then
    _RET=
  else
    show_change_mode_usage
    fail "Wrong destination mode"
  fi
}

show_change_mode_usage(){
  log_info "Usage: change_mode.sh [current | testing | off]"
}