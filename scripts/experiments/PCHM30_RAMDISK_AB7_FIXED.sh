#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "[ERROR] line=$LINENO rc=$rc cmd=$BASH_COMMAND" >&2' ERR

WIN="/mnt/c/Users/user/Downloads"
ROOT="/root/twrp-12.1-pchm30"
WORK="/root/pchm30-ramdisk-ab7-fixed"

AB5="$WIN/PCHM30-OrangeFox-RAMDISK-AB5-GOLDEN-QCOMRC-FSTAB-MERGE-A2-BASE.img"
A2="$WIN/PCHM30-OrangeFox-12.1-BOOTFLOW-A2-recovery.img"

OUT_NAME="PCHM30-OrangeFox-RAMDISK-AB7-PREPDECRYPT-NO-CRYPTO-RESTART.img"
DEST="$WIN/$OUT_NAME"

PARTITION_SIZE=67108864

EXPECT_AB5="c237be06d9977736306cf5af0ad590058943a34b62c2606840b056edf6c041ed"
EXPECT_KERNEL="39ce9b538651d76859546d102053aaef0a8c228b272dac701cc456b090e03544"
EXPECT_DTBO="b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270"

die() { echo "[FATAL] $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

for x in python3 gzip sha256sum stat grep head cmp awk; do need "$x"; done

[ -f "$AB5" ] || die "Missing AB5: $AB5"
[ -f "$A2" ] || die "Missing A2: $A2"

AB5_SHA="$(sha256sum "$AB5" | awk '{print $1}')"
[ "$AB5_SHA" = "$EXPECT_AB5" ] || die "AB5 SHA256 mismatch: $AB5_SHA"

UNPACK="$ROOT/system/tools/mkbootimg/unpack_bootimg.py"
MKBOOTIMG="$ROOT/system/tools/mkbootimg/mkbootimg.py"
[ -f "$UNPACK" ] || die "unpack_bootimg.py missing"
[ -f "$MKBOOTIMG" ] || die "mkbootimg.py missing"

AVB=""
for x in \
  "$ROOT/external/avb/avbtool" \
  "$ROOT/external/avb/avbtool.py" \
  "$ROOT/out/host/linux-x86/bin/avbtool"; do
    [ -f "$x" ] && { AVB="$x"; break; }
done
[ -n "$AVB" ] || die "avbtool missing"

KEY="$ROOT/external/avb/test/data/testkey_rsa4096.pem"
[ -f "$KEY" ] || die "RSA4096 AVB key missing"

avb() {
    if head -c 2 "$AVB" 2>/dev/null | grep -q '^#!'; then
        python3 "$AVB" "$@"
    else
        "$AVB" "$@"
    fi
}

rm -rf "$WORK"
mkdir -p "$WORK/ab5" "$WORK/a2" "$WORK/ab7" "$WORK/final" "$WORK/verify"

echo "============================================================"
echo " PCHM30 RAMDISK AB7 FIXED"
echo " BASE = reviewed AB5"
echo " ONLY NEW VARIABLE = pchm30-bootflow-a2.sh restart tail"
echo " BUILD ONLY"
echo "============================================================"
echo

echo "===== 1/8 UNPACK ====="
python3 "$UNPACK" --boot_img "$AB5" --out "$WORK/ab5"
python3 "$UNPACK" --boot_img "$A2" --out "$WORK/a2"

K="$(sha256sum "$WORK/ab5/kernel" | awk '{print $1}')"
D="$(sha256sum "$WORK/ab5/recovery_dtbo" | awk '{print $1}')"
[ "$K" = "$EXPECT_KERNEL" ] || die "AB5 kernel drift"
[ "$D" = "$EXPECT_DTBO" ] || die "AB5 DTBO drift"
echo "kernel=$K"
echo "dtbo=$D"
echo

echo "===== 2/8 DECOMPRESS AB5 RAMDISK ====="
gzip -dc "$WORK/ab5/ramdisk" > "$WORK/ab5/ramdisk.cpio"
sha256sum "$WORK/ab5/ramdisk.cpio"
echo

echo "===== 3/8 PATCH EXACTLY ONE CPIO PAYLOAD ====="
python3 - "$WORK/ab5/ramdisk.cpio" "$WORK/ab7/ramdisk.cpio" "$WORK/ab7/report.txt" <<'PY'
from pathlib import Path
import hashlib, sys

SRC=Path(sys.argv[1])
DST=Path(sys.argv[2])
REPORT=Path(sys.argv[3])
TARGET="system/bin/pchm30-bootflow-a2.sh"

MARKER="# Mirror the manually-proven service order, but NEVER stop/restart Recovery in A2."

def a4(n): return (n+3)&~3

class Entry:
    def __init__(self,hdr,name,data):
        self.hdr=bytearray(hdr)
        self.name_raw=name
        self.data=data
    @property
    def path(self):
        n=self.name_raw[:-1] if self.name_raw.endswith(b"\0") else self.name_raw
        s=n.decode("utf-8",errors="surrogateescape")
        while s.startswith("./"): s=s[2:]
        return s
    def set_size(self):
        self.hdr[54:62]=f"{len(self.data):08x}".encode("ascii")

def parse(blob):
    entries=[]; off=0; tail=b""
    while True:
        if off+110>len(blob): raise RuntimeError(f"truncated CPIO header at {off}")
        h=blob[off:off+110]
        if h[:6] not in (b"070701",b"070702"):
            raise RuntimeError(f"bad CPIO magic at {off}: {h[:6]!r}")
        size=int(h[54:62],16); namesz=int(h[94:102],16)
        off+=110
        name=blob[off:off+namesz]; off+=namesz; off=a4(off)
        data=blob[off:off+size]; off+=size; off=a4(off)
        e=Entry(h,name,data); entries.append(e)
        if e.path=="TRAILER!!!":
            tail=blob[off:]; break
    return entries,tail

def serialize(entries,tail):
    out=bytearray()
    for e in entries:
        e.set_size()
        out+=e.hdr
        out+=e.name_raw
        while len(out)%4: out.append(0)
        out+=e.data
        while len(out)%4: out.append(0)
    out+=tail
    return bytes(out)

old_blob=SRC.read_bytes()
entries,tail=parse(old_blob)
hits=[e for e in entries if e.path==TARGET]
if len(hits)!=1:
    raise SystemExit(f"[FATAL] expected one {TARGET}, found {len(hits)}")

e=hits[0]
old_sha=hashlib.sha256(e.data).hexdigest()
text=e.data.decode("utf-8",errors="surrogateescape")

required=[
    "stage wait_ui_crypto_type",
    "/system/bin/pchm30-precrypto.sh",
    "setprop prepdecrypt.setpatch false",
    "setprop keymaster_ver 4.0",
    "setprop vendor.gatekeeper.disable_spu true",
    "setprop crypto.ready 0",
    "start hwservicemanager",
    "stage prepdecrypt",
    "start prepdecrypt",
    "getprop crypto.ready",
    MARKER,
    "stop keystore2",
    "stop gatekeeper-1-0-qti",
    "stop keymaster-4-0-qti",
    "stop qseecomd",
]
for x in required:
    if x not in text:
        raise SystemExit("[FATAL] expected AB5 bootflow content missing: "+x)

pos=text.find(MARKER)
front=text[:pos]

new_tail='''# AB7 controlled experiment:
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
'''

new_text=front+new_tail

must_keep=[
    "stage wait_ui_crypto_type",
    "/system/bin/pchm30-precrypto.sh",
    "setprop prepdecrypt.setpatch false",
    "setprop keymaster_ver 4.0",
    "setprop vendor.gatekeeper.disable_spu true",
    "setprop crypto.ready 0",
    "start hwservicemanager",
    "stage prepdecrypt",
    "start prepdecrypt",
    "getprop crypto.ready",
]
for x in must_keep:
    if x not in new_text:
        raise SystemExit("[FATAL] front-half lost: "+x)

for x in [
    "stop keystore2",
    "stop gatekeeper-1-0-qti",
    "stop keymaster-4-0-qti",
    "stop qseecomd",
    "start qseecomd",
    "start keymaster-4-0-qti",
    "start gatekeeper-1-0-qti",
    "start keystore2",
    "rm -rf /tmp/keymaster_key_blob",
]:
    if x in new_text:
        raise SystemExit("[FATAL] restart command remains: "+x)

e.data=new_text.encode("utf-8",errors="surrogateescape")
new_blob=serialize(entries,tail)
DST.write_bytes(new_blob)

old_entries,_=parse(old_blob)
new_entries,_=parse(new_blob)
if len(old_entries)!=len(new_entries):
    raise SystemExit("[FATAL] CPIO entry count changed")

changes=[]
for a,b in zip(old_entries,new_entries):
    if a.path!=b.path: raise SystemExit("[FATAL] CPIO path order changed")
    if a.hdr[:54]!=b.hdr[:54]: raise SystemExit("[FATAL] metadata drift before filesize: "+a.path)
    if a.hdr[62:]!=b.hdr[62:]: raise SystemExit("[FATAL] metadata drift after filesize: "+a.path)
    if a.data!=b.data: changes.append(a.path)

if changes!=[TARGET]:
    raise SystemExit("[FATAL] changed payload set != [TARGET]: "+repr(changes))

final=next(x for x in new_entries if x.path==TARGET)
new_sha=hashlib.sha256(final.data).hexdigest()

report=f'''============================================================
AB7 CPIO SEMANTIC FORENSIC REPORT
============================================================
Base: reviewed AB5
CPIO entry count: {len(new_entries)}
Changed payload count: 1
Changed: {TARGET}
AB5-before: {old_sha}
AB7-final:  {new_sha}

RETAINED:
  wait_ui_crypto_type
  pchm30-precrypto
  prepdecrypt
  crypto.ready wait
  bootflow autostart via existing rc

REMOVED:
  stop/start qseecomd
  stop/start keymaster
  stop/start gatekeeper
  stop/start keystore2
  rm -rf /tmp/keymaster_key_blob

PASS: ONLY ONE CPIO FILE PAYLOAD CHANGED.
All other AB5 CPIO entries retained.
'''
REPORT.write_text(report)
print(report)
PY

echo
echo "===== 4/8 RECOMPRESS ====="
gzip -9n < "$WORK/ab7/ramdisk.cpio" > "$WORK/ab7/ramdisk"
AB7_RAMDISK_SHA="$(sha256sum "$WORK/ab7/ramdisk" | awk '{print $1}')"
echo "AB7 ramdisk=$AB7_RAMDISK_SHA"
echo

echo "===== 5/8 PARSE A2 HEADER ====="
python3 - "$A2" "$WORK/a2-boot.env" <<'PY'
from pathlib import Path
import struct,shlex,sys
b=Path(sys.argv[1]).read_bytes(); h=b[:4096]
if h[:8]!=b"ANDROID!": raise SystemExit("bad A2 boot magic")
u32=lambda o:struct.unpack_from("<I",h,o)[0]
osf=u32(44)
maj=(osf>>25)&0x7f; mi=(osf>>18)&0x7f; pa=(osf>>11)&0x7f
yr=((osf>>4)&0x7f)+2000; mo=osf&0xf
cmd=(h[64:576].split(b"\0",1)[0]+h[608:1632].split(b"\0",1)[0]).decode("latin1")
vals={"HEADER_VERSION":str(u32(40)),"PAGE_SIZE":str(u32(36)),
      "OS_VERSION":f"{maj}.{mi}.{pa}","OS_PATCH":f"{yr:04d}-{mo:02d}","CMDLINE":cmd}
Path(sys.argv[2]).write_text("\n".join(f"{k}={shlex.quote(v)}" for k,v in vals.items())+"\n")
PY
source "$WORK/a2-boot.env"
[ "$HEADER_VERSION" = "1" ] || die "header != 1"
[ "$PAGE_SIZE" = "4096" ] || die "pagesize != 4096"
echo "header=$HEADER_VERSION pagesize=$PAGE_SIZE os=$OS_VERSION patch=$OS_PATCH"
echo

echo "===== 6/8 MKBOOTIMG ====="
RAW="$WORK/final/unsigned.img"
python3 "$MKBOOTIMG" \
  --kernel "$WORK/ab5/kernel" \
  --ramdisk "$WORK/ab7/ramdisk" \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --pagesize 4096 \
  --header_version 1 \
  --os_version "$OS_VERSION" \
  --os_patch_level "$OS_PATCH" \
  --cmdline "$CMDLINE" \
  --recovery_dtbo "$WORK/ab5/recovery_dtbo" \
  --output "$RAW"

[ "$(stat -c %s "$RAW")" -lt "$PARTITION_SIZE" ] || die "unsigned AB7 too large"
echo

echo "===== 7/8 CLONE A2 AVB POLICY ====="
python3 - "$A2" "$WORK/a2-avb.env" <<'PY'
from pathlib import Path
import struct,shlex,sys
b=Path(sys.argv[1]).read_bytes()
if b[-64:-60]!=b"AVBf": raise SystemExit("A2 AVB footer missing")
orig,vbo,vbs=struct.unpack_from(">QQQ",b,len(b)-52)
if b[vbo:vbo+4]!=b"AVB0": raise SystemExit("A2 AVB0 missing")
h=b[vbo:vbo+256]
auth,aux=struct.unpack_from(">QQ",h,12)
alg=struct.unpack_from(">I",h,28)[0]
rollback=struct.unpack_from(">Q",h,112)[0]
flags=struct.unpack_from(">I",h,120)[0]
desc_off,desc_size=struct.unpack_from(">QQ",h,96)
aux_start=vbo+256+auth
D=b[aux_start+desc_off:aux_start+desc_off+desc_size]
salt=""; part=""; dflags=""; props=[]; pos=0
while pos+16<=len(D):
    tag,n=struct.unpack_from(">QQ",D,pos); chunk=D[pos:pos+16+n]
    if tag==2:
        body=chunk[16:]
        pname_len,salt_len,digest_len,df=struct.unpack_from(">IIII",body,40)
        var=body[116:]; part=var[:pname_len].decode()
        salt=var[pname_len:pname_len+salt_len].hex(); dflags=str(df)
    elif tag==0:
        ks,vs=struct.unpack_from(">QQ",chunk,16); st=32
        k=chunk[st:st+ks].decode(); vst=st+ks+1; v=chunk[vst:vst+vs].decode()
        props.append((k,v))
    pos+=16+n
seen=set(); uniq=[]
for x in props:
    if x not in seen: seen.add(x); uniq.append(x)
vals={"ALG":str(alg),"ROLLBACK":str(rollback),"FLAGS":str(flags),
      "DESC_FLAGS":dflags,"PART":part,"SALT":salt,"PROP_COUNT":str(len(uniq))}
lines=[f"{k}={shlex.quote(v)}" for k,v in vals.items()]
for i,(k,v) in enumerate(uniq):
    lines += [f"PROP_{i}_KEY={shlex.quote(k)}",f"PROP_{i}_VAL={shlex.quote(v)}"]
Path(sys.argv[2]).write_text("\n".join(lines)+"\n")
PY
source "$WORK/a2-avb.env"
[ "$ALG" = "2" ] || die "unexpected AVB algorithm"
[ "$ROLLBACK" = "1" ] || die "unexpected rollback index"
[ "$FLAGS" = "0" ] || die "unexpected AVB flags"
[ "$DESC_FLAGS" = "0" ] || die "unexpected descriptor flags"
[ "$PART" = "recovery" ] || die "unexpected partition"

SIGNED="$WORK/final/$OUT_NAME"
cp -f "$RAW" "$SIGNED"
ARGS=(
  add_hash_footer
  --image "$SIGNED"
  --partition_size "$PARTITION_SIZE"
  --partition_name recovery
  --hash_algorithm sha256
  --algorithm SHA256_RSA4096
  --key "$KEY"
  --rollback_index 1
  --salt "$SALT"
)
for ((i=0;i<PROP_COUNT;i++)); do
    kvar="PROP_${i}_KEY"; vvar="PROP_${i}_VAL"
    ARGS+=(--prop "${!kvar}:${!vvar}")
done
avb "${ARGS[@]}"
[ "$(stat -c %s "$SIGNED")" -eq "$PARTITION_SIZE" ] || die "signed AB7 != 64 MiB"
echo

echo "===== 8/8 FINAL FORENSIC VERIFY ====="
python3 "$UNPACK" --boot_img "$SIGNED" --out "$WORK/verify" >/dev/null
VK="$(sha256sum "$WORK/verify/kernel" | awk '{print $1}')"
VD="$(sha256sum "$WORK/verify/recovery_dtbo" | awk '{print $1}')"
VR="$(sha256sum "$WORK/verify/ramdisk" | awk '{print $1}')"
echo "verify kernel  = $VK"
echo "verify dtbo    = $VD"
echo "verify ramdisk = $VR"
[ "$VK" = "$EXPECT_KERNEL" ] || die "final kernel changed"
[ "$VD" = "$EXPECT_DTBO" ] || die "final DTBO changed"
[ "$VR" = "$AB7_RAMDISK_SHA" ] || die "final ramdisk changed"

gzip -dc "$WORK/verify/ramdisk" > "$WORK/verify/ramdisk.cpio"
cmp -s "$WORK/verify/ramdisk.cpio" "$WORK/ab7/ramdisk.cpio" || die "final CPIO mismatch"

cat "$WORK/ab7/report.txt"

cp -f "$SIGNED" "$DEST"
FINAL_SHA="$(sha256sum "$DEST" | awk '{print $1}')"

echo
echo "============================================================"
echo " PASS: RAMDISK-AB7 READY FOR FORENSIC REVIEW"
echo "============================================================"
echo "Base AB5 SHA256: $EXPECT_AB5"
echo
echo "ONLY NEW CHANGE VS AB5:"
echo "  system/bin/pchm30-bootflow-a2.sh"
echo "  prepdecrypt front-half retained"
echo "  post-prepdecrypt crypto-stack restart removed"
echo
echo "Windows image:"
echo "  C:\\Users\\user\\Downloads\\$OUT_NAME"
echo
echo "SHA256:"
echo "  $FINAL_SHA"
echo
echo "BUILD ONLY. DO NOT BOOT OR FLASH YET."
echo "============================================================"
