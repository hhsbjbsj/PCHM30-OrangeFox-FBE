#!/usr/bin/env python3
"""Rebuild a checked PCHM30 Recovery ramdisk; never flash or claim SDK upgrade."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,struct
from image_format import Record,aligned,boot_parts,parse_cpio,serialize_cpio,abi_preflight
BASE=Path(__file__).resolve().parent
KERNEL='d83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b'
DTBO='b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270'
sha=lambda b:hashlib.sha256(b).hexdigest()

def build(source,output,kind):
    raw=source.read_bytes();kernel,ramdisk,dtbo=boot_parts(raw)
    assert sha(kernel)==KERNEL and sha(dtbo)==DTBO,'Not the verified PCHM30 kernel/DTBO'
    original={r.name:r for r in parse_cpio(gzip.decompress(ramdisk))}
    assert sha(original['system/bin/recovery'].data)=='67c2609e3003e504c0bb9e11d479e21d7ee04455034782e26aa62d90395542e7','Input TWRP executable differs from the supplied V4 baseline'
    assert b'ro.build.version.sdk=32' in original['prop.default'].data.splitlines(),'Do not mix an unverified newer UI/runtime'
    overlays=BASE/'device/recovery/root'
    provenance=json.loads((BASE/'BUSYBOX-PROVENANCE.json').read_text())
    assert sha((overlays/'sbin/busybox').read_bytes())==provenance['sha256']
    result=dict(original);changed=[]
    def set_record(name,data,mode):
        if name in result:
            fields=result[name].fields.copy();fields[1]=mode
        else:fields=[0,mode,0,0,1,0,0,0,0,0,0,0,0]
        result[name]=Record(name,fields,data);changed.append(name)
    def parents(name):
        p=Path(name).parent
        for parent in reversed(p.parents):
            s=parent.as_posix()
            if s not in ('.','/') and s not in result:set_record(s,b'',0o40755)
        s=p.as_posix()
        if s not in ('.','/') and s not in result:set_record(s,b'',0o40755)
    for p in sorted(overlays.rglob('*')):
        if not p.is_file():continue
        name=p.relative_to(overlays).as_posix();parents(name)
        set_record(name,p.read_bytes(),0o100755 if p.name=='busybox' or p.suffix=='.sh' else 0o100644)
    # Use a static shell for ZIP installation, independent of mounted Android /system.
    set_record('sbin/sh',b'busybox',0o120777)
    marker={'kind':kind,'built_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_image_sha256':sha(raw),'base_sdk':32,'sdk_upgrade_performed':False,'busybox_sha256':provenance['sha256'],'data_policy':'ext4 fscrypt v1 wrappedkey; DE keys remain /data/unencrypted/key','metadata_keydirectory_repointed':False,'phone_boot_tested':False,'decryption_fixed_verified':False,'changed_paths':sorted(changed)}
    set_record('system/etc/pchm30-a16-recovery-fix.json',(json.dumps(marker,indent=2)+'\n').encode(),0o100644)
    inventory=('ramdisk-files.txt','ramdisk-files.sha256sum')
    for name in inventory:result.pop(name,None)
    set_record(inventory[0],('\n'.join(sorted(result))+ '\n'+'\n'.join(inventory)+'\n').encode(),0o100644)
    sums=''.join(sha(r.data)+'  ./'+r.name+'\n' for r in result.values() if r.mode&0xf000==0x8000)
    set_record(inventory[1],sums.encode(),0o100644)
    for name,record in original.items():
        if name not in changed:assert result[name].data==record.data and result[name].mode==record.mode,name
    assert not any(b'setprop prepdecrypt.setpatch false' in r.data for n,r in result.items() if n.endswith(('.rc','.sh'))),'A startup hook still forces setpatch false'
    assert b'/system_root ext4 ro' in result['system/etc/recovery.fstab'].data
    assert b' /data ext4 ' in result['system/etc/recovery.fstab'].data
    assert b'keydirectory=/data/' not in result['system/etc/recovery.fstab'].data
    assert b'ro.build.version.sdk=32' in result['prop.default'].data.splitlines()
    dependency_counts=abi_preflight(list(result.values()))
    cpio=serialize_cpio(list(result.values()));parsed=parse_cpio(cpio)
    assert [(r.name,r.mode,r.data) for r in parsed]==[(r.name,r.mode,r.data) for r in result.values()]
    compressed=gzip.compress(cpio,compresslevel=9,mtime=0)
    header=bytearray(raw[:4096]);offset=4096+aligned(len(kernel))+aligned(len(compressed))
    struct.pack_into('<I',header,16,len(compressed));struct.pack_into('<Q',header,1636,offset)
    boot_id=hashlib.sha1()
    for part in (kernel,compressed,b'',dtbo):boot_id.update(part);boot_id.update(struct.pack('<I',len(part)))
    header[576:608]=boot_id.digest()+bytes(12)
    image=bytes(header)+kernel+bytes((-len(kernel))%4096)+compressed+bytes((-len(compressed))%4096)+dtbo+bytes((-len(dtbo))%4096)
    assert len(image)<=67108864
    assert boot_parts(image)==(kernel,compressed,dtbo)
    assert original['system/bin/recovery'].data==result['system/bin/recovery'].data
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(image)
    report=dict(marker,image=output.name,sha256=sha(image),bytes=len(image),boot_id_valid=True,kernel_unchanged=True,dtbo_unchanged=True,all_original_runtime_libraries_unchanged=True,dependency_counts=dependency_counts,static_shell_present=True)
    output.with_suffix('.img.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    output.with_suffix('.img.sha256').write_text(sha(image)+'  '+output.name+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--kind',choices=['ramdisk-rebuild-from-tested-image','cnb-source-build-plus-device-overlay'],default='ramdisk-rebuild-from-tested-image');a=p.parse_args()
    build(a.input,a.output,a.kind)
