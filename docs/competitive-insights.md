# Competitive Insights

## Market Context

AI transcription products have validated demand for audio-to-score workflows. AgentClef uses that demand as a foundation and focuses on the review layer that turns an imperfect draft into a confirmed score.

## Reference Products

| Product | Relevant Capability | AgentClef Application |
| :--- | :--- | :--- |
| Songscription | Audio upload, AI draft, PDF/MIDI/MusicXML/GuitarPro export | Establishes automatic draft generation as a baseline capability |
| Klangio | Instrument-specific transcription modes and multi-view transcription | Informs future model routing and instrument-specific adapters |
| AnthemScore | Desktop transcription and audio-note editing | Informs local note review and evidence-based editing |
| Melody Scanner | Online editing, piano roll, notation, tab views | Informs multi-view draft representation |
| Soundslice | Audio-score sync, looping, slow playback | Directly informs workbench review interactions |
| Moises | Stem separation, chord detection, speed and pitch tools | Informs later musician assistance features |
| Chordify | Chord timeline, transpose, practice loop | Informs optional chord review and lead-sheet workflows |
| RipX / Samplab | Note-level audio editing and audio-to-MIDI workflows | Informs long-term note-level audio interaction research |
| OMR tools | PDF/image score recognition and MusicXML export | Informs future audio + existing-score alignment |

## Product Differentiation

AgentClef differentiates through the review loop:

```text
AI draft
-> synchronized evidence
-> uncertainty markers
-> local selection
-> Agent reasoning
-> CandidateEdit preview
-> user confirmation
-> revision log
```

## v0.1 Adopted Patterns

- AI-generated draft as a starting point.
- Workbench-style audio and score context.
- Local review instead of global chat.
- Candidate edits instead of direct AI mutation.
- Revision records for applied changes.

## Future Reference Areas

- Stronger audio-score sync inspired by Soundslice.
- Chord timeline and transposition inspired by Chordify.
- Stem-assisted review inspired by Moises.
- Instrument-specific pipelines inspired by Klangio.
- Existing score alignment inspired by OMR tools.
