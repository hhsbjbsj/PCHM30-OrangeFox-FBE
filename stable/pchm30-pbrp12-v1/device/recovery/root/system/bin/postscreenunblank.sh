#!/system/bin/sh
NODE=/sys/kernel/oppo_display/notify_panel_blank
[ -e "$NODE" ] && echo 1 > "$NODE"
exit 0
