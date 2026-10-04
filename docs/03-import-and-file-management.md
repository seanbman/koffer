# 3. Import and File Management

Koffer separates indexing from file management. A Sample can be useful inside Koffer without first being copied into a managed directory.

## Reference
Reference keeps the audio file at its existing filesystem location.

Use Reference when the source library is already organized, the file belongs to another project or application, duplication is unnecessary, or Koffer is being used primarily as an index.

## Copy
Copy creates a new file inside a Koffer-managed library while leaving the original untouched.

Before copying, Koffer should show source path, destination, filename, detected conflicts, and expected operation.

A copy may also receive edited descriptive metadata such as title, artist/author, album, genre, comments, and embedded artwork without modifying the source file.

## Move
Move relocates the existing file into the Koffer-managed library.

Because Move changes the filesystem, it must be clearly identified before execution. A move should never be implied by adding a tag, accepting a suggestion, or adding a Sample to a Collection.

## Metadata writes
Metadata writes are separate from ordinary Koffer library tagging.

When the user changes embeddable metadata, Koffer should offer an explicit target:
- **Update Original** — write supported fields into the existing file.
- **Write to Copy** — preserve the original and apply metadata to a copied or rendered file.

Fields may include title, artist/author, album, album artist, genre, year/date, comments, composer, copyright, track numbering, and embedded artwork where supported by the file format.

Changing Koffer-only classification or Collection membership must never rewrite a source file automatically.

## Conflicts
When a destination filename already exists, Koffer must never silently overwrite it.

Possible actions:
- keep both using a generated name;
- choose another destination;
- skip;
- compare likely duplicates;
- replace only after explicit confirmation.

## Duplicate awareness
Koffer should attempt to identify duplicate or near-duplicate files using exact file identity where possible, content hash, duration, technical properties, and optional audio similarity.

Duplicate detection informs the user rather than automatically deleting material.

## Managed library structure
The physical structure of the managed library is an implementation detail and should not become the user's primary navigation model.

Users organize material through metadata, search, and Collections even if files are stored in conventional directories underneath.

## Batch operations
Reference, Copy, Move, and supported metadata updates should work on one or many selected Samples.

Batch operations should provide a review step showing exceptions, format limitations, and conflicts before destructive changes occur.
