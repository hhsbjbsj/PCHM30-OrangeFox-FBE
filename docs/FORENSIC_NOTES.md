# PCHM30 OrangeFox FBE forensic notes

## Known-good outer components

Golden and A2 were confirmed to use the same kernel and recovery DTBO.

Kernel SHA256:

```text
39ce9b538651d76859546d102053aaef0a8c228b272dac701cc456b090e03544
```

Recovery DTBO SHA256:

```text
b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270
```

The decisive differences were inside the recovery ramdisk.

## Controlled experiments

### AB1

A2 outer image + exact Golden ramdisk.

Result:

- Normal OrangeFox boot
- Normal decryption

Conclusion:

The primary fault domain was inside the ramdisk rather than kernel, DTBO, boot header,
cmdline, or outer AVB layout.

### AB2

A2 baseline with exact Golden:

- `system/bin/merge-fstab.sh`
- `system/etc/recovery.fstab`

Result:

- Recovery UI booted normally
- `/sdcard` only exposed the Fox directory
- User FBE keys were not installed

### AB5

Added exact Golden:

- `init.recovery.qcom.rc`

while retaining the AB2 Golden fstab pair.

Result:

- Recovery booted normally
- User-space/media namespace became visible
- Filenames remained encrypted/scrambled

This showed that the QCOM recovery init environment materially affected access to
userdata, but did not by itself complete FBE unlock.

### AB6

AB5 with A2 bootflow late-init autostart disabled.

Result:

- Stuck on the Recovery entry screen

Conclusion:

The A2 bootflow front half was still required for the current hybrid startup path.

### AB7

AB5 with the A2 bootflow front half retained:

- precrypto
- prepdecrypt
- wait for `crypto.ready=1`

but with the post-prepdecrypt qsee/keymaster/gatekeeper/keystore2 stop/start cycle removed.

Result:

- Recovery booted normally
- Filenames were still encrypted

Conclusion:

The second crypto-stack restart was not the decisive FBE failure.

### AB8

AB7 plus exact Golden:

- `system/etc/init/keystore2.rc`

Result:

- Recovery booted normally
- Filenames were still encrypted

Conclusion:

`keystore2.rc` alone was not the decisive FBE variable.

### AB9

AB8 plus exact Golden:

- `system/bin/keystore2`

Result:

- Recovery booted normally
- Filenames were still encrypted

Conclusion:

The `keystore2` binary alone was not the decisive FBE variable.

### AB10 — working

Returned to the AB8 baseline and changed only:

- `system/bin/recovery` -> exact Golden binary payload

Result:

- Recovery booted normally
- `/data` was accessible
- `/sdcard` displayed real filenames
- Android 11 FBE decryption succeeded

Final image SHA256:

```text
b3d1b6a6d711e95b8b10cf0bbe33eed5ea82cff6ce845183af9210ccc6ebb14b
```

## Current interpretation

The experiments show two separate requirements:

1. The Golden fstab / QCOM init environment is important for reaching the correct
   userdata and Qualcomm crypto environment.
2. The decisive change that converted visible-but-encrypted user data into successfully
   decrypted FBE data was the Golden `system/bin/recovery` binary.

This repository intentionally preserves the controlled-variable history so later cleanup
can remove unnecessary experimental scaffolding without losing the evidence that led to
the working build.
