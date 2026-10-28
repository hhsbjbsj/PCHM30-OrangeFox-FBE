#!/system/bin/sh
LOG=/tmp/pchm30-bootflow-a2.log
: > "$LOG"

say(){ echo "$(date 2>/dev/null) $*" >> "$LOG"; }
stage(){ setprop pchm30.bootflow.stage "$1"; say "STAGE=$1"; }

wait_svc(){
    name="$1"; limit="$2"; i=0
    while [ "$i" -lt "$limit" ]; do
        [ "$(getprop init.svc.$name)" = "running" ] && return 0
        sleep 1
        i=$((i+1))
    done
    return 1
}

# UI/Recovery is the primary boot path. Do not touch crypto before it has
# initialized ro.crypto.state=encrypted and ro.crypto.type=file.
stage wait_ui_crypto_type
i=0
while [ "$i" -lt 75 ]; do
    rec="$(getprop init.svc.recovery)"
    cstate="$(getprop ro.crypto.state)"
    ctype="$(getprop ro.crypto.type)"
    if [ "$rec" = "running" ] && [ "$cstate" = "encrypted" ] && [ "$ctype" = "file" ]; then
        say "UI ready: recovery=$rec state=$cstate type=$ctype"
        break
    fi
    sleep 1
    i=$((i+1))
done

if [ "$i" -ge 75 ]; then
    say "TIMEOUT: UI left untouched; ro.crypto.type=file never became ready"
    setprop pchm30.bootflow.result ui_ok_crypto_type_timeout
    exit 0
fi

stage precrypto
/system/bin/pchm30-precrypto.sh >> "$LOG" 2>&1 || true
setprop prepdecrypt.setpatch true
setprop keymaster_ver 4.0
setprop vendor.gatekeeper.disable_spu true

# Force a clean 0 -> 1 transition for the qcom property chain.
setprop crypto.ready 0
start hwservicemanager

stage prepdecrypt
start prepdecrypt
j=0
while [ "$j" -lt 20 ]; do
    [ "$(getprop crypto.ready)" = "1" ] && break
    sleep 1
    j=$((j+1))
done

if [ "$(getprop crypto.ready)" != "1" ]; then
    say "ERROR: prepdecrypt failed; Recovery/UI left running"
    setprop pchm30.bootflow.result prepdecrypt_failed_ui_ok
    exit 0
fi
say "prepdecrypt complete: crypto.ready=1"

# AB7 controlled experiment:
# prepdecrypt already completed and crypto.ready=1.
# Keep the current QCOM crypto-service state; do not tear it down.

stage prepdecrypt_ready_no_restart
say "AB7: prepdecrypt ready; crypto-stack restart skipped"

say "qsee=$(getprop init.svc.qseecomd)"
say "keymaster=$(getprop init.svc.keymaster-4-0-qti)"
say "gatekeeper=$(getprop init.svc.gatekeeper-1-0-qti)"
say "keystore2=$(getprop init.svc.keystore2)"
say "recovery=$(getprop init.svc.recovery)"

NODE=/sys/kernel/oppo_display/notify_panel_blank
[ -e "$NODE" ] && echo 1 > "$NODE"

stage done
setprop pchm30.bootflow.result prepdecrypt_ready_no_restart
say "AB7 complete: no crypto-stack restart"
exit 0
