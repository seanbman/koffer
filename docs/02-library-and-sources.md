# 2. Library and Sources

## Adding a Source
Users can add one or more directories for Koffer to scan.

A Source may contain individual audio files, sample packs, recordings, project exports, nested folders, or mounted external storage.

Adding a Source does not reorganize or rename its contents.

## Scanning
Koffer scans Sources recursively by default and records path, filename, format, duration, sample rate, bit depth where available, channel count, file size, and modification state.

Additional musical analysis may occur after discovery.

## Exclusions
Users should be able to exclude specific subdirectories, hidden directories, unsupported content, or patterns they do not want indexed.

## Rescanning
Koffer should distinguish between new files, unchanged files, changed files, and missing files.

Unchanged audio should not require full analysis every time a Source is scanned.

## External storage
Sources may live on removable drives.

If a drive is unavailable, Koffer keeps the library records but clearly marks affected Samples as offline or unavailable rather than silently removing them.

## Missing files
When a referenced file cannot be found, Koffer should offer:
- locate the file;
- locate the containing Source;
- remove the stale library entry;
- rescan the Source.

## Source management
Each Source should expose display name, filesystem path, scan status, last scan, file count, exclusions, enable/disable state, rescan action, and remove-from-Koffer action.

Removing a Source from Koffer must not delete the Source directory or its audio files.
