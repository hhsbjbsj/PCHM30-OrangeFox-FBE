# Final AB10 build manifest

## Final image

```text
PCHM30-OrangeFox-RAMDISK-AB10-GOLDEN-RECOVERY-BINARY.img
```

SHA256:

```text
b3d1b6a6d711e95b8b10cf0bbe33eed5ea82cff6ce845183af9210ccc6ebb14b
```

Size:

```text
67108864 bytes
```

## AB10 base

AB8 SHA256:

```text
cd002d42c7e7453720c797df5636d52892514d31307a13b297fd223da2bd08a2
```

## AB10 controlled change relative to AB8

Only one new CPIO payload was changed:

```text
system/bin/recovery
```

The AB8/A2 recovery binary was replaced with the exact Golden recovery binary payload.

Inherited from AB8:

- A2 
- Golden 
- Golden 
- Golden 
- Golden 
- AB7 no-crypto-restart bootflow
- all other ramdisk binaries and files
- kernel / recovery DTBO / header / cmdline policy

## Test result

AB10 was tested by temporary .

Observed result:

- OrangeFox UI entered normally
- touch worked
- user storage decrypted
- normal  filenames were visible
