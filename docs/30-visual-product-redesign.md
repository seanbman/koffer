# 30. Visual Product Redesign

## Goal

Koffer should look like a deliberately designed music-production utility: dark, tactile, colorful, dense, readable, and technically serious. It must not look like a database admin tool, a settings form, or a default Qt demo.

The interface should make audio, classification, and user actions visually dominant. Internal implementation detail should recede.

## Visual personality

Keywords:

- dark studio hardware;
- clay/orange Koffer identity;
- electric blue analysis;
- violet/purple edit state;
- green confirmed/safe;
- warm yellow review/warning;
- red destructive/failure;
- cyan playback/time;
- compact high-information surfaces;
- subtle depth, not glossy skeuomorphism.

The application remains professional. “More color” means meaningful accent layers, not rainbow decoration.

## Expanded token palette

Existing neutral tokens remain. Add:

| Token | Suggested value | Meaning |
|---|---:|---|
| Clay | #CF8652 | brand, primary action |
| Clay Bright | #E7A36F | primary hover/focus |
| Electric Blue | #6FA3D8 | analysis, Suggestions |
| Cyan | #54C6D8 | playback, time, waveform playhead |
| Violet | #9B7BD8 | edit/workbench state, recipe |
| Magenta | #C66AA3 | pitch/key/tonal controls |
| Green | #67B983 | confirmed, online, saved, safe |
| Yellow | #D7B65E | pending review, warning |
| Red | #D36B6B | destructive/error |
| Teal | #5FB7A2 | Collections/organization |
| Canvas | #0B0D0F | application background |
| Surface 1 | #121518 | nav/panels |
| Surface 2 | #181C20 | cards |
| Surface 3 | #20252A | hover/selected support |
| Surface 4 | #272D33 | raised editor controls |

All status color also has text/icon/shape redundancy.

## Accent ownership

Colors have stable jobs:

- Clay = “do the main thing”.
- Blue = machine analysis / unconfirmed suggestion.
- Violet = non-destructive sound editing.
- Cyan = playback/time/waveform playhead.
- Magenta = pitch/key/tonal values.
- Green = user-confirmed or safely saved.
- Teal = organization / Collection membership.
- Yellow = needs review.
- Red = destructive or failed.

Do not arbitrarily recolor each button.

## Shell composition

Reference 1440×900:

- top bar: 42 px;
- left navigation: 220–236 px;
- main content: flexible;
- optional Inspector: 330–360 px;
- transport: 74–82 px.

The shell uses a restrained accent strip or selected-nav marker. Avoid giant blank title regions.

### Top bar

Contains:

- Koffer mark/name;
- current workspace/breadcrumb;
- compact global analysis/activity status;
- optional local/offline badge only when meaningful.

Do not place feature actions here unless global.

### Navigation

Use icon + label rows with compact counts/badges.

Recommended accents:

- Library: Clay;
- Favourites: Magenta or Clay;
- Review: Blue/Yellow;
- Collections: Teal;
- Sources: Green;
- Activity: Cyan;
- Settings: neutral.

Selection uses background + 2–3 px accent edge. Hover is a lighter neutral surface, not another bright color.

### Transport

The transport is a visually coherent hardware-like strip:

- large play/pause;
- restart;
- current Sample title;
- elapsed/total time;
- seek bar;
- loop indicator;
- preview gain;
- output/device status only when relevant.

Cyan playhead/seek accent. Violet appears when a modified recipe preview is active.

## Button hierarchy

Every screen must define exactly:

- primary action;
- secondary actions;
- tertiary/menu actions;
- destructive actions.

Primary uses filled Clay, except editor-specific “Save Recipe” may use Violet if the operation is non-destructive and “Export” remains Clay.

Secondary uses Surface 3 + border and may use colored icon/text.

Destructive is isolated and red.

Do not line up six same-weight buttons.

When more than four actions exist, move low-frequency actions into a clearly labeled overflow menu or context menu.

## Cards and sections

Use cards only for meaningful groups:

- Classification;
- Suggestions;
- File Details;
- Collections;
- Artwork;
- Edit controls;
- Analysis status.

A card has:

- short header;
- optional status badge;
- content;
- at most one compact action row.

Do not wrap every label in a card.

## Plain-language content rule

Normal screens show:

- “Kick · One-shot · Percussive”
- “AI suggestion: Kick 94%”
- “120 BPM · C minor”
- “44.1 kHz · 24-bit · mono”
- “In 3 Collections”
- “Edited: trim + normalize”

They do not show:

- `provider=panns model_version=...`;
- serialized JSON;
- database IDs;
- raw enum names;
- full evidence dictionaries.

Technical detail can be expanded intentionally.

## Classification chips

Classification values use chips:

- confirmed classification: Green outline/fill tint;
- machine suggestion: Blue;
- user tag: Clay-neutral;
- genre/style: Magenta tint;
- role: Violet tint.

Chips must have readable labels and editable/remove behavior where permitted.

## Analysis state

Use a compact Analysis capsule:

- Not analyzed — neutral;
- Queued — Cyan;
- Analyzing — animated/progress Blue;
- Suggestions ready — Blue with count;
- Reviewed — Green;
- Failed — Red;
- Model needed — Yellow.

Clicking opens Review/Analysis Details, not a raw text dump.

## Waveform styling

Waveform is a major visual object, not a tiny preview.

Default waveform:

- dark surface;
- neutral waveform body;
- cyan playhead;
- Violet retained region in Edit Sound;
- dim excluded trim regions;
- Clay/Violet trim handles;
- yellow transient/beat markers only when enabled;
- loop region with translucent Cyan/Violet tint;
- fade envelopes as visible curves;
- selection state obvious without reading numbers.

## Forms

Avoid “wall of labels + spin boxes”.

Use compact grouped controls:

- two-column parameter strips;
- segmented buttons;
- knobs only when they improve usability and remain keyboard-accessible;
- sliders for gain/zoom where appropriate;
- editable numeric values next to sliders;
- dropdowns for discrete formats.

Long text areas are reserved for actual long-form text, such as comments. They are not a container for diagnostics.

## Sample screen composition

The Sample surface is visually divided into:

1. identity and artwork;
2. large waveform;
3. immediate playback/edit actions;
4. classification and Suggestions;
5. Collections/tags;
6. File Details collapsed summary.

The primary actions are:

- **Edit Sound**;
- **Edit Info**;
- **Find Similar**;
- **Add to Collection**.

“Reveal in Files” and Organize are tertiary/context actions.

## Workbench composition

The editor gets the largest waveform in the product.

Layout:

- top: Sample name + dirty/saved state + Back;
- center: waveform editor;
- under waveform: transport + zoom/selection readout;
- right or bottom control dock grouped as:
  - Trim & Fade;
  - Level;
  - Pitch & Time;
  - Direction;
  - Output;
- footer: Reset, A/B, Save Recipe, Export Copy.

Do not make the user scroll through 20 form rows to edit a sound.

## Suggestions Review composition

Left: review queue.

Center: Sample identity + waveform/preview.

Right: proposed classifications as friendly cards/chips with confidence and “Why?” disclosure.

Primary keyboard actions remain Accept, Edit & Accept, Reject.

Raw evidence lives under “Why this suggestion?” and is translated into sentences such as:

- “The local audio model strongly detected bass drum.”
- “The filename contains ‘kick’.”
- “The sound is short and strongly percussive.”

## Responsive desktop behavior

At narrower desktop widths:

1. Inspector collapses;
2. auxiliary card columns stack;
3. labels shorten;
4. browser remains dominant.

Never shrink waveform/editor handles below usable size.

## Visual completion checklist

A screen fails visual acceptance if any of these are true:

- default Qt appearance dominates;
- more than one unrelated action row exists;
- primary action is unclear;
- raw debug content appears by default;
- giant dead space exists;
- controls are aligned inconsistently;
- bright colors have no semantic meaning;
- waveform is secondary on an audio-editing screen;
- important values are buried in paragraphs;
- destructive action is visually adjacent to safe primary action;
- the user must understand internal architecture to use the screen.
