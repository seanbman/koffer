# 5. Sample Classification and Metadata

Koffer uses several independent metadata dimensions rather than forcing every Sample into one category tree.

## Sample Type
Describes the structural form or intended sampling use.

Initial vocabulary:
- One-shot
- Loop
- Phrase
- Stem
- Track
- Texture
- Ambience
- SFX

## Instrument / Source
Describes what is heard or what produced the sound.

Examples:
- Kick
- Snare
- Clap
- Hi-hat
- Cymbal
- Percussion
- Drum kit
- Bass
- Guitar
- Keys
- Piano
- Rhodes
- Organ
- Synth
- Strings
- Brass
- Woodwind
- Vocal
- Foley
- Field recording

More specific labels may coexist with broader ones. A Sample can therefore be both **Kick** and **Drum**.

## Musical Role
Initial vocabulary:
- Percussive
- Rhythmic
- Melodic
- Harmonic
- Atmospheric
- Transitional
- Vocal
- Effect

## Genre / Style
Genre and style are descriptive tags rather than exclusive folders.

Examples include Hip-hop, House, Techno, Jungle, Drum and bass, Ambient, Funk, Soul, Rock, and Jazz.

Multiple styles may apply.

## Character
Character describes perceived sonic qualities.

Examples include Dark, Bright, Warm, Cold, Clean, Dirty, Lo-fi, Acoustic, Electronic, Distorted, Dry, Wet, Soft, and Aggressive.

Character should remain extensible because descriptive language differs between users.

## Musical metadata
Where meaningful:
- BPM;
- tempo confidence;
- key;
- mode;
- tuning offset;
- time-signature information where reliably known.

## Descriptive file metadata
Koffer should support reading and editing descriptive metadata embedded in compatible audio formats.

Examples include:
- title;
- artist / author;
- album;
- album artist;
- genre;
- track number;
- year / date;
- comment / description;
- composer;
- copyright;
- embedded cover / album artwork.

Not every audio format supports every field. Koffer should expose only operations the selected file format can safely store.

## Metadata write modes
Metadata editing should support two explicit write targets.

### Update in place
Koffer writes supported metadata back to the existing audio file.

Because this changes the source file, the UI must identify the action clearly before writing. Updating tags in place should not alter the decoded audio content itself.

### Write to copy
Koffer creates or updates a copied/rendered file with the chosen metadata while leaving the source file untouched.

This should be the preferred workflow when the user wants to preserve original source material.

## Album artwork
Where the format supports embedded artwork, users should be able to:
- view existing artwork;
- add or replace artwork;
- remove artwork;
- write the artwork in place;
- carry artwork into a copied or rendered file.

Koffer may also display external artwork discovered alongside a file, but external artwork and artwork embedded in the audio file must be distinguishable.

## Technical metadata
Koffer records factual file properties separately from musical classification:
- format;
- sample rate;
- bit depth;
- channel count;
- duration;
- file size.

Technical properties should not be presented as ordinary editable tags when changing them would require an audio render or conversion.

## User tags
Users may add free-form tags for vocabulary that does not belong in a formal category.

Koffer-library tags do not need to be embedded into the audio file unless the user explicitly chooses a supported metadata write operation.

## Confirmed vs suggested metadata
Koffer should visually distinguish extracted factual metadata, embedded file metadata, Koffer suggestions, user-confirmed classifications, and user-created tags.

The user should always be able to revise a classification or editable metadata field later.
