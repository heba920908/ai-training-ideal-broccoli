# band-introduction Specification

## Purpose
Produce the approved Spanish concert introduction for Septima Ola through EPAM DIAL, preserving clean narration and a separate atmospheric MP3 mix made locally with imageio-ffmpeg.

## Requirements

### Requirement: Approved Spanish introduction
The script SHALL introduce Séptima Ola using the approved Spanish reggae/jazz narration, naming Ciudad de México, Valle de Chalco, Coacalco, and Puerto Rico, and ending with Con ustedes and the band name.

#### Scenario: Default narration
- **WHEN** T4-1 runs with defaults
- **THEN** the speech request contains the approved introduction without spoken effects directions.

### Requirement: DIAL speech with local effects
The script SHALL reuse environment-based DIAL configuration and the existing three-candidate resolver, preserve clean speech, and render a separate MP3 with synthetic atmospheric effects and echo.

#### Scenario: Successful generation
- **WHEN** a deployed candidate returns audio
- **THEN** clean speech, narration, and a playable final mix are saved in the selected output directory.

#### Scenario: No compatible deployment
- **WHEN** no candidate returns audio
- **THEN** the script fails clearly rather than reporting success.

### Requirement: Reproducible execution
The README SHALL document dependencies, invocation, customization, output paths, and limitations without requiring a system FFmpeg installation.

#### Scenario: Documented execution
- **WHEN** the user loads the existing OPENAI environment and runs the documented command
- **THEN** requests and imageio-ffmpeg suffice without extra provider credentials.

### Requirement: Optional background track and Nova default
The script SHALL default to nova and accept an optional local background_audio parameter and --background-audio CLI option. A supplied track SHALL replace the synthetic bed, loop or trim to the existing mix duration, and use quiet levels and fades while retaining voice echo. Without a track the original synthetic bed SHALL remain available.

#### Scenario: Short or long background
- **WHEN** a valid track is supplied
- **THEN** it plays beneath narration for the mix duration regardless of its original length, and clean speech remains unchanged.

#### Scenario: Invalid input before generation
- **WHEN** the background is missing, corrupt, or has no decodable audio
- **THEN** the script fails before making a DIAL request.

#### Scenario: Default voice
- **WHEN** no voice argument is supplied through Python or the CLI
- **THEN** nova is selected.

### Requirement: Reproducible A2 sample
The README SHALL include a runnable FFmpeg command creating a pulsing A2 110 Hz sample and an example using it as a background, and SHALL explain installed FFmpeg preference and bundled fallback.

#### Scenario: Local sample demonstration
- **WHEN** the sample is mixed with existing Nova clean speech
- **THEN** a decodable final MP3 is produced without another DIAL request.
