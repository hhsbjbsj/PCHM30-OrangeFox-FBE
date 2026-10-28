#!/usr/bin/env python3
"""Replace only a guarded PCHM30 ZIP installer; leave every image byte intact."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    source=a.input.resolve();output=a.output.resolve()
    assert source!=output and source.is_file() and not output.exists()
    partial=output.with_name(output.name+'.partial');assert not partial.exists()
    member='META-INF/com/google/android/update-binary'
    new_script=(Path(__file__).resolve().parent/'update-binary.sh').read_bytes()
    copied={}
    with zipfile.ZipFile(source) as old,zipfile.ZipFile(partial,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as new:
        assert len(old.namelist())==len(set(old.namelist()))
        for required in ['chunks.list','partition-sizes.list','final-files.list',member]:assert required in old.namelist()
        assert 'PCHM30' in old.read(member).decode() and b'Never writes GPT' in old.read(member),'Unknown installer family'
        for info in old.infolist():
            print('Copying',info.filename,flush=True)
            if info.filename==member:
                target=zipfile.ZipInfo(member);target.create_system=3;target.external_attr=0o100755<<16;new.writestr(target,new_script)
                continue
            h=hashlib.sha256();count=0
            # Preserve size/mode/method, stream instead of buffering raw images.
            with old.open(info) as src,new.open(info,'w',force_zip64=info.file_size>=zipfile.ZIP64_LIMIT) as dst:
                while data:=src.read(8*1024**2):dst.write(data);h.update(data);count+=len(data)
            copied[info.filename]=(count,h.hexdigest())
    with zipfile.ZipFile(partial) as new:
        assert new.read(member)==new_script
        for name,(size,expected) in copied.items():
            h=hashlib.sha256();count=0
            with new.open(name) as f:
                while data:=f.read(8*1024**2):h.update(data);count+=len(data)
            assert count==size and h.hexdigest()==expected,name
    partial.rename(output)
    h=hashlib.sha256()
    with output.open('rb') as f:
        while data:=f.read(8*1024**2):h.update(data)
    output.with_suffix('.zip.sha256').write_text(h.hexdigest()+'  '+output.name+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'only_changed_member':member,'all_other_members_verified_unchanged':len(copied),'phone_modified':False,'system_recompiled':False},indent=2))

if __name__=='__main__':main()
