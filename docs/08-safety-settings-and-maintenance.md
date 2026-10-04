# 8. Safety, Settings, and Library Maintenance

## File-operation safety
Operations that change the filesystem must be more explicit than ordinary library actions.

Koffer should confirm moves, replacements, destructive cleanup, and bulk changes with filesystem consequences.

Tagging, classification, Collection membership, and non-destructive preparation should not alter source files.

## Library location
Users should be able to choose where Koffer stores its database, managed audio, waveform/analysis cache, and temporary renders.

## Cache
Waveforms, embeddings, and derived analysis may be cached so Koffer does not repeat expensive work unnecessarily.

The user should be able to clear rebuildable caches without losing confirmed metadata or Collections.

## Analysis settings
Settings may include automatic analysis on discovery, background-analysis limits, model enable/disable, deeper analysis only while idle, and similarity indexing.

## Rebuilding the index
Koffer should offer a controlled way to rebuild filesystem-derived state while preserving user-created organization wherever possible.

## Changed files
If a file has changed outside Koffer, the application should detect the mismatch and offer to refresh analysis rather than silently treating old analysis as current.

## Backups
The library database contains valuable organization even when original audio exists elsewhere.

Koffer should make its database location clear and eventually provide a simple backup/export mechanism.

## Privacy and networking
The planned default is local operation.

Audio analysis and inference should work without uploading the user's files.

Any future network-connected capability must be clearly identifiable and optional.
