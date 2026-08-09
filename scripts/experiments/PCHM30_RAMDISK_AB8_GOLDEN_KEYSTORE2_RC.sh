#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "[ERROR] line=$LINENO rc=$rc cmd=$BASH_COMMAND" >&2' ERR

WIN="/mnt/c/Users/user/Downloads"
ROOT="/root/twrp-12.1-pchm30"
WORK="/root/pchm30-ramdisk-ab8"

AB7="$WIN/PCHM30-OrangeFox-RAMDISK-AB7-PREPDECRYPT-NO-CRYPTO-RESTART.img"
GOLDEN="$WIN/PCHM30-GOLDEN-HYBRID-recovery.img"

OUT_NAME="PCHM30-OrangeFox-RAMDISK-AB8-GOLDEN-KEYSTORE2-RC.img"
DEST="$WIN/$OUT_NAME"

PARTITION_SIZE=67108864

EXPECT_AB7="9708f3a7c4ba7c3814116a63a44920ed0524c60d03bd618649f2f9213ee51078"
EXPECT_GOLDEN="d0cfcd0a73c3ef9bd884435ac5462f04b899ac920018ac5a78c56c9b119b7f18"
EXPECT_KERNEL="39ce9b538651d76859546d102053aaef0a8c228b272dac701cc456b090e03544"
EXPECT_DTBO="b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270"

die(){ echo "[FATAL] $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

for x in python3 gzip sha256sum stat grep head cmp awk; do need "$x"; done

[ -f "$AB7" ] || die "Missing AB7: $AB7"
[ -f "$GOLDEN" ] || die "Missing Golden: $GOLDEN"

AB7_SHA="$(sha256sum "$AB7" | awk '{print $1}')"
GOLDEN_SHA="$(sha256sum "$GOLDEN" | awk '{print $1}')"

[ "$AB7_SHA" = "$EXPECT_AB7" ] || die "AB7 SHA mismatch: $AB7_SHA"
[ "$GOLDEN_SHA" = "$EXPECT_GOLDEN" ] || die "Golden SHA mismatch: $GOLDEN_SHA"

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

avb(){
    if head -c 2 "$AVB" 2>/dev/null | grep -q '^#!'; then
        python3 "$AVB" "$@"
    else
        "$AVB" "$@"
    fi
}

rm -rf "$WORK"
mkdir -p "$WORK/ab7" "$WORK/golden" "$WORK/ab8" "$WORK/final" "$WORK/verify"

echo "============================================================"
echo " PCHM30 RAMDISK AB8"
echo " BASE = tested AB7"
echo " ONLY NEW CHANGE = Golden system/etc/init/keystore2.rc"
echo " BUILD ONLY"
echo "============================================================"
echo
echo "AB7    = $AB7_SHA"
echo "Golden = $GOLDEN_SHA"
echo

echo "===== 1/8 UNPACK AB7 + GOLDEN ====="
python3 "$UNPACK" --boot_img "$AB7" --out "$WORK/ab7"
python3 "$UNPACK" --boot_img "$GOLDEN" --out "$WORK/golden"

K="$(sha256sum "$WORK/ab7/kernel" | awk '{print $1}')"
D="$(sha256sum "$WORK/ab7/recovery_dtbo" | awk '{print $1}')"
[ "$K" = "$EXPECT_KERNEL" ] || die "AB7 kernel drift"
[ "$D" = "$EXPECT_DTBO" ] || die "AB7 DTBO drift"
echo "kernel=$K"
echo "dtbo=$D"
echo

echo "===== 2/8 DECOMPRESS RAMDISKS ====="
gzip -dc "$WORK/ab7/ramdisk" > "$WORK/ab7/ramdisk.cpio"
gzip -dc "$WORK/golden/ramdisk" > "$WORK/golden/ramdisk.cpio"
echo "AB7 CPIO:"
sha256sum "$WORK/ab7/ramdisk.cpio"
echo "Golden CPIO:"
sha256sum "$WORK/golden/ramdisk.cpio"
echo

echo "===== 3/8 PATCH EXACTLY ONE CPIO PAYLOAD ====="
python3 - \
  "$WORK/ab7/ramdisk.cpio" \
  "$WORK/golden/ramdisk.cpio" \
  "$WORK/ab8/ramdisk.cpio" \
  "$WORK/ab8/report.txt" <<'PY'
from pathlib import Path
import hashlib, sys

AB7=Path(sys.argv[1])
GOLDEN=Path(sys.argv[2])
OUT=Path(sys.argv[3])
REPORT=Path(sys.argv[4])

TARGET="system/etc/init/keystore2.rc"

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
    out=[]; off=0; tail=b""
    while True:
        if off+110>len(blob):
            raise RuntimeError(f"truncated CPIO at {off}")
        h=blob[off:off+110]
        if h[:6] not in (b"070701",b"070702"):
            raise RuntimeError(f"bad CPIO magic at {off}: {h[:6]!r}")
        size=int(h[54:62],16)
        namesz=int(h[94:102],16)
        off+=110
        name=blob[off:off+namesz]
        off+=namesz
        off=a4(off)
        data=blob[off:off+size]
        off+=size
        off=a4(off)
        e=Entry(h,name,data)
        out.append(e)
        if e.path=="TRAILER!!!":
            tail=blob[off:]
            break
    return out,tail

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

ab7_blob=AB7.read_bytes()
gold_blob=GOLDEN.read_bytes()

ab7_entries,tail=parse(ab7_blob)
gold_entries,_=parse(gold_blob)

amap={e.path:e for e in ab7_entries}
gmap={e.path:e for e in gold_entries}

if TARGET not in amap:
    raise SystemExit("[FATAL] AB7 missing "+TARGET)
if TARGET not in gmap:
    raise SystemExit("[FATAL] Golden missing "+TARGET)

before=hashlib.sha256(amap[TARGET].data).hexdigest()
gold_sha=hashlib.sha256(gmap[TARGET].data).hexdigest()

if amap[TARGET].data == gmap[TARGET].data:
    raise SystemExit("[FATAL] AB7 keystore2.rc already equals Golden; experiment would be meaningless")

# Payload only: preserve AB7 CPIO entry metadata/order.
amap[TARGET].data=gmap[TARGET].data

new_blob=serialize(ab7_entries,tail)
OUT.write_bytes(new_blob)

old_entries,_=parse(ab7_blob)
new_entries,_=parse(new_blob)

if len(old_entries)!=len(new_entries):
    raise SystemExit("[FATAL] CPIO entry count changed")

changes=[]
for a,b in zip(old_entries,new_entries):
    if a.path!=b.path:
        raise SystemExit("[FATAL] path/order changed")
    if a.hdr[:54]!=b.hdr[:54]:
        raise SystemExit("[FATAL] metadata drift before filesize: "+a.path)
    if a.hdr[62:]!=b.hdr[62:]:
        raise SystemExit("[FATAL] metadata drift after filesize: "+a.path)
    if a.data!=b.data:
        changes.append(a.path)

if changes != [TARGET]:
    raise SystemExit("[FATAL] changed set != [TARGET]: "+repr(changes))

final=next(e for e in new_entries if e.path==TARGET)
final_sha=hashlib.sha256(final.data).hexdigest()

if final_sha != gold_sha:
    raise SystemExit("[FATAL] AB8 keystore2.rc not exact Golden payload")

report=f'''============================================================
AB8 CPIO SEMANTIC FORENSIC REPORT
============================================================
Base: tested AB7
CPIO entry count: {len(new_entries)}
Changed payload count: 1
Changed: {TARGET}

AB7-before = {before}
Golden     = {gold_sha}
AB8-final  = {final_sha}
RESULT     = EXACT GOLDEN PAYLOAD

PASS: ONLY ONE CPIO FILE PAYLOAD CHANGED.
All other AB7 CPIO entries retained.
'''
REPORT.write_text(report)
print(report)
PY

echo
echo "===== 4/8 RECOMPRESS ====="
gzip -9n < "$WORK/ab8/ramdisk.cpio" > "$WORK/ab8/ramdisk"
AB8_RAMDISK_SHA="$(sha256sum "$WORK/ab8/ramdisk" | awk '{print $1}')"
echo "AB8 ramdisk=$AB8_RAMDISK_SHA"
echo

echo "===== 5/8 PARSE AB7 HEADER ====="
python3 - "$AB7" "$WORK/ab7-boot.env" <<'PY'
from pathlib import Path
import struct,shlex,sys
b=Path(sys.argv[1]).read_bytes(); h=b[:4096]
if h[:8]!=b"ANDROID!": raise SystemExit("bad AB7 boot magic")
u32=lambda o:struct.unpack_from("<I",h,o)[0]
osf=u32(44)
maj=(osf>>25)&0x7f; mi=(osf>>18)&0x7f; pa=(osf>>11)&0x7f
yr=((osf>>4)&0x7f)+2000; mo=osf&0xf
cmd=(h[64:576].split(b"\0",1)[0]+h[608:1632].split(b"\0",1)[0]).decode("latin1")
vals={"HEADER_VERSION":str(u32(40)),"PAGE_SIZE":str(u32(36)),
      "OS_VERSION":f"{maj}.{mi}.{pa}","OS_PATCH":f"{yr:04d}-{mo:02d}","CMDLINE":cmd}
Path(sys.argv[2]).write_text("\n".join(f"{k}={shlex.quote(v)}" for k,v in vals.items())+"\n")
PY
source "$WORK/ab7-boot.env"
[ "$HEADER_VERSION" = "1" ] || die "header != 1"
[ "$PAGE_SIZE" = "4096" ] || die "pagesize != 4096"
echo "header=$HEADER_VERSION pagesize=$PAGE_SIZE os=$OS_VERSION patch=$OS_PATCH"
echo

echo "===== 6/8 MKBOOTIMG ====="
RAW="$WORK/final/unsigned.img"
python3 "$MKBOOTIMG" \
  --kernel "$WORK/ab7/kernel" \
  --ramdisk "$WORK/ab8/ramdisk" \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --pagesize 4096 \
  --header_version 1 \
  --os_version "$OS_VERSION" \
  --os_patch_level "$OS_PATCH" \
  --cmdline "$CMDLINE" \
  --recovery_dtbo "$WORK/ab7/recovery_dtbo" \
  --output "$RAW"

[ "$(stat -c %s "$RAW")" -lt "$PARTITION_SIZE" ] || die "unsigned AB8 too large"
echo

echo "===== 7/8 CLONE AB7 AVB POLICY ====="
python3 - "$AB7" "$WORK/ab7-avb.env" <<'PY'
from pathlib import Path
import struct,shlex,sys
b=Path(sys.argv[1]).read_bytes()
if b[-64:-60]!=b"AVBf": raise SystemExit("AB7 AVB footer missing")
orig,vbo,vbs=struct.unpack_from(">QQQ",b,len(b)-52)
if b[vbo:vbo+4]!=b"AVB0": raise SystemExit("AB7 AVB0 missing")
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
    tag,n=struct.unpack_from(">QQ",D,pos)
    chunk=D[pos:pos+16+n]
    if tag==2:
        body=chunk[16:]
        pname_len,salt_len,digest_len,df=struct.unpack_from(">IIII",body,40)
        var=body[116:]
        part=var[:pname_len].decode()
        salt=var[pname_len:pname_len+salt_len].hex()
        dflags=str(df)
    elif tag==0:
        ks,vs=struct.unpack_from(">QQ",chunk,16)
        st=32
        k=chunk[st:st+ks].decode()
        vst=st+ks+1
        v=chunk[vst:vst+vs].decode()
        props.append((k,v))
    pos+=16+n
seen=set(); uniq=[]
for x in props:
    if x not in seen:
        seen.add(x); uniq.append(x)
vals={"ALG":str(alg),"ROLLBACK":str(rollback),"FLAGS":str(flags),
      "DESC_FLAGS":dflags,"PART":part,"SALT":salt,"PROP_COUNT":str(len(uniq))}
lines=[f"{k}={shlex.quote(v)}" for k,v in vals.items()]
for i,(k,v) in enumerate(uniq):
    lines += [f"PROP_{i}_KEY={shlex.quote(k)}",f"PROP_{i}_VAL={shlex.quote(v)}"]
Path(sys.argv[2]).write_text("\n".join(lines)+"\n")
PY
source "$WORK/ab7-avb.env"

[ "$ALG" = "2" ] || die "unexpected AVB algorithm"
[ "$ROLLBACK" = "1" ] || die "unexpected rollback index"
[ "$FLAGS" = "0" ] || die "unexpected AVB flags"
[ "$DESC_FLAGS" = "0" ] || die "unexpected descriptor flags"
[ "$PART" = "recovery" ] || die "unexpected AVB partition"

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
    kvar="PROP_${i}_KEY"
    vvar="PROP_${i}_VAL"
    ARGS+=(--prop "${!kvar}:${!vvar}")
done

avb "${ARGS[@]}"
[ "$(stat -c %s "$SIGNED")" -eq "$PARTITION_SIZE" ] || die "signed AB8 != 64 MiB"
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
[ "$VR" = "$AB8_RAMDISK_SHA" ] || die "final ramdisk changed"

gzip -dc "$WORK/verify/ramdisk" > "$WORK/verify/ramdisk.cpio"
cmp -s "$WORK/verify/ramdisk.cpio" "$WORK/ab8/ramdisk.cpio" || die "final CPIO mismatch"

cat "$WORK/ab8/report.txt"

cp -f "$SIGNED" "$DEST"
FINAL_SHA="$(sha256sum "$DEST" | awk '{print $1}')"

echo
echo "============================================================"
echo " PASS: RAMDISK-AB8 READY FOR FORENSIC REVIEW"
echo "============================================================"
echo "Base AB7 SHA256:"
echo "  $EXPECT_AB7"
echo
echo "ONLY NEW CHANGE VS AB7:"
echo "  system/etc/init/keystore2.rc"
echo "  AB7/A2 -> exact Golden payload"
echo
echo "AB7 bootflow modification retained."
echo "Golden qcom rc/fstab/merge inherited from AB7."
echo "All binaries retained from AB7."
echo
echo "Windows image:"
echo "  C:\\Users\\user\\Downloads\\$OUT_NAME"
echo
echo "SHA256:"
echo "  $FINAL_SHA"
echo
echo "BUILD ONLY. DO NOT BOOT OR FLASH YET."
echo "============================================================"
