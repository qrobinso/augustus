# Voicebox TTS provider and provider-scoped casts

Date: 2026-09-27
Status: draft for review

## Goal

Generate briefings with the cloned voices on any self-hosted Voicebox server.
The first server to use is `http://192.168.4.44:17493` (Voicebox API 0.5.0), but
nothing in the design is specific to that server. Make casts belong to a TTS
provider so that the cast list always matches the voices that the active
provider can speak.

Success means:

1. Enter a Voicebox server URL in Settings, select Voicebox, select a model (such as Chatterbox Turbo), and
   test the connection.
2. Create a cast by selecting "Dad" and "Kevin" from a voice list instead of
   pasting IDs.
3. Generate a briefing that plays in those voices, with correct chapters and
   transcript timings.
4. Switch the provider to Gemini: the Casts page and every cast picker list
   only Gemini casts, and the Voicebox casts remain available for the next
   switch back.

## Decisions made in brainstorming

- The TTS provider remains one global setting. Voicebox becomes the fourth
  option beside Piper, ElevenLabs, and Gemini.
- Every cast belongs to exactly one provider. The active provider determines
  which casts are usable.
- Augustus does not create casts automatically. If the active provider has no
  cast, briefing generation fails with a clear message. The UI warns before
  that happens.
- Voicebox synthesis runs line by line. Augustus downloads each WAV and stitches
  the WAVs itself (approach A), rather than using Voicebox Stories.

## Delivery

The work ships as two commits on `main`, each with its own tests and version
bump:

1. **Provider-scoped casts.** This commit works with the three existing
   providers.
2. **Voicebox provider.** This commit adds Voicebox, its settings, and its
   voice list.

## Part 1: Provider-scoped casts

### Data

- Add `casts.tts_provider VARCHAR(32) NOT NULL`, with one of the values
  `piper`, `elevenlabs`, `gemini`, or `voicebox`.
- Add the migration module `app/migrations/add_tts_provider_to_casts.py`. It is
  idempotent: it checks `PRAGMA table_info` before it alters the table. It can
  run on its own like the other migrations, and `init_db()` also calls it, so
  Docker users need no manual step.
- The migration backfills existing casts by inferring the provider from the
  voice IDs of the cast members:
  - Every voice is in the Gemini voice catalog (`Kore`, `Puck`, `Zephyr`, …):
    `gemini`.
  - Any voice is a 20-character alphanumeric ElevenLabs ID: `elevenlabs`.
  - Any voice looks like Kokoro or Piper (`af_heart`, `am_eric`, blends that
    contain `:` or `,`, or `en_US-*`): `piper`.
  - Anything else: the provider configured in `TTS_PROVIDER` when the
    migration runs.
- Default casts are unique per profile and provider. `_unset_default_casts`,
  `set_default_cast`, and `get_default_cast` all take the provider into
  account.

### Service rules (`CastService`)

- `create_cast` stamps the active provider on the new cast. A client cannot
  choose a different provider. The first cast created for a profile and
  provider becomes that provider's default.
- `get_user_casts(provider=...)` defaults to the active provider. The
  `provider="all"` option returns every cast, for the "other providers" section
  of the Casts page.
- `get_default_cast(provider)` no longer creates a Gemini cast when none
  exists. If casts exist for the provider but none is marked default, it
  selects the oldest cast and marks it default. If the provider has no casts,
  it raises `NoCastForProviderError`, with a message such as: "No Voicebox cast
  yet. Create one on the Casts page."
- `set_default_cast` rejects a cast that belongs to another provider.
- Seeding the cast for a new profile (`_seed_default_cast`) keeps the Gemini
  voices and stamps the cast `tts_provider="gemini"`.
- Restore default (the Kore and Puck voices) applies only to Gemini. The UI
  hides the button for the other providers.

### Resolving the cast at generation time

A single helper, `resolve_cast_for_generation(requested_cast_id, implicit)`,
replaces the lookup in `services/briefing.py` step 5 and is used by every
entry point:

| Source of the cast | Cast belongs to the active provider | Cast belongs to another provider, or no cast given |
|---|---|---|
| Explicit: API `cast_id`, MCP `generate_briefing`, a breakout's `cast_id` | Use it | Return HTTP 400: "'Gemini Pro Cast' is a Gemini cast; your voice provider is Voicebox." This check runs at request time, before the briefing is queued. |
| Implicit: schedule's cast, breakout parent's cast | Use it | Use the active provider's default and log the fallback |
| None | n/a | Use the active provider's default |

If there is no default, the briefing fails with the `NoCastForProviderError`
message, which appears on the briefing like other generation errors. On-demand
requests (generate, breakout) fail early with HTTP 400 and the same message, so
the request is rejected before it is queued. A scheduled briefing can only fail
at generation time.

The MCP `regenerate_audio` tool points at `/api/briefings/{id}/regenerate-audio`,
but that route does not exist in the backend. That gap predates this work and is
out of scope here.

### API

- `CastResponse` gains the `tts_provider` field.
- `GET /api/casts?provider=all` lists the casts of every provider.
- `GET /api/casts/voices` returns
  `{provider, voices: [{id, name, description}], allows_custom: bool}` for the
  active provider. Each provider's `list_voices()` supplies the list.
  `allows_custom` is true for Piper and ElevenLabs, whose built-in catalogs are
  partial, and false for Gemini and Voicebox.
- `GET /api/casts/summary` returns the number of casts per provider for the
  current profile. The Settings page uses it for its hint. It lives in the casts
  router because the counts depend on the profile.
- MCP `list_casts` includes `tts_provider` and states in its description that
  only active-provider casts are listed.

### UI

- **Casts page**
  - A header line reads "**Voicebox casts** · voices from your active provider
    · Change in Settings", with a provider badge.
  - The list shows only casts for the active provider.
  - If the active provider has no casts, an empty state reads "No Voicebox
    casts yet. Briefings need one before they can play." It has a **Create
    cast** button.
  - A collapsed section, "4 casts for other providers", lists the remaining
    casts dimmed, each with a provider badge. You can view or delete them, but
    not set them as default or use them.
- **Cast editor**
  - A badge reads "These hosts use **Voicebox** voices".
  - The Voice ID text box becomes a voice dropdown fed by `/api/casts/voices`.
  - When `allows_custom` is true, a "Custom voice ID…" entry reveals the text
    box.
  - Editing a cast for another provider opens read-only, with the note "Switch
    to Gemini in Settings to edit this cast."
  - Member cards show voice names instead of raw IDs.
- **Settings.** Under the provider cards, a hint shows the cast count for the
  selected provider: "3 Gemini casts" or "No Voicebox casts yet. Create one
  before your next briefing →".
- **Cast pickers** in CreateSchedule, BreakoutDialog, DashboardGenerate, and
  DashboardSchedules list only the active provider's casts. A schedule whose
  saved cast belongs to another provider shows "Uses your default Voicebox
  cast". The saved cast is kept and not rewritten.

## Part 2: Voicebox provider

### Settings

- Add the environment and settings fields `VOICEBOX_URL` and
  `VOICEBOX_MODEL`. Both are exposed through `/api/settings` in the same way as
  the Piper and Gemini fields.
  - `VOICEBOX_URL` has no default. The Settings field shows
    `http://localhost:17493`, the Voicebox default port, as a placeholder.
    Voicebox cannot be saved as the provider until a URL is set, in the same
    way that ElevenLabs and Gemini require an API key.
  - `VOICEBOX_MODEL` defaults to the first downloaded TTS model that the
    instance reports.
- `GET /api/settings/voicebox/models` proxies `GET /models/status`. It returns
  only the downloaded TTS models, excluding Whisper and the LLM models.
- `POST /api/settings/validate/voicebox` checks `GET /health` and reads the
  API version from `GET /openapi.json`. It reports the version and the number
  of voice profiles. If the version is older than 0.5.0, the version this
  design was tested against, it returns a warning and does not block saving.
- The Settings UI adds a fourth provider card, "Voicebox". The card contains a
  URL field, a **Test connection** button, and a model dropdown.
- The backend maps a model name to Voicebox request fields with the static
  table below. A model that the table does not contain, such as one added in a
  later Voicebox release, is logged and left out of the model dropdown. It does
  not cause an error. The table is the only part of the design that must change
  when Voicebox adds engines:

| Model | `engine` | `model_size` |
|---|---|---|
| qwen-tts-1.7B / 0.6B | `qwen` | `1.7B` / `0.6B` |
| qwen-custom-voice-1.7B / 0.6B | `qwen_custom_voice` | `1.7B` / `0.6B` |
| luxtts | `luxtts` | — |
| chatterbox-tts | `chatterbox` | — |
| chatterbox-turbo | `chatterbox_turbo` | — |
| tada-1b / tada-3b-ml | `tada` | `1B` / `3B` |
| kokoro | `kokoro` | — |
| breeze-tts-2 | `breeze` | — |

### Provider (`services/tts/voicebox.py`)

`VoiceboxProvider(TTSProvider)` is registered in `TTSFactory` as `voicebox`.

- `list_voices()` calls `GET /profiles` and returns one `Voice` for each
  profile, with `id` set to the profile ID and `name` set to the profile name.
  The result is cached for the lifetime of the provider instance.
- **Voice resolution.** A cast voice ID matches a profile by its ID, or else by
  its name, compared case-insensitively and with surrounding whitespace
  trimmed. The name match is needed because a profile is named `"Halie "`. If
  nothing matches, the provider raises the error "'Zephyr' isn't a Voicebox
  voice. Edit the cast."
- **Engine choice.** A preset profile (`voice_type == "preset"`) uses its
  `preset_engine`, because presets cannot run on other engines. Every other
  profile uses the model from Settings.
- **Per line**, the provider does the following:
  1. Send `POST /generate` with `{profile_id, text, language: profile.language,
     engine, model_size}`.
  2. Wait on the server-sent event stream `GET /generate/{id}/status` until
     the status is `completed` or `failed`. This replaces a polling loop. If
     the stream ends without either status, fall back to one read of
     `GET /history/{id}`.
  3. Stream the audio from `GET /audio/{id}`, which returns a WAV, to a file on
     disk.
  4. Send `DELETE /history/{id}` so that briefings do not fill the Voicebox
     history.

  Each line times out after 300 s, which allows for the first model load.
- **Cancellation.** Before each line, the provider checks the briefing's
  cancellation flag. If a briefing is cancelled while a line is generating, it
  sends `POST /generate/{id}/cancel` and deletes that history item.
- **Stitching.** Stitching streams to disk. `pydub` loads one line at a time,
  converts it to the first line's frame rate and sample width in mono (engines
  can differ in sample rate), and appends it to a single output WAV. Only one
  line is in memory at a time. Consecutive lines are joined with a 250 ms gap. The result is exported to WAV and converted with
  `app.utils.audio.convert_to_mp3`. If MP3 conversion is unavailable, the
  provider keeps the WAV, as Piper does. `SegmentTiming` values come from the
  accumulated segment durations.
- **Generation order.** Lines render with bounded concurrency:
  `VOICEBOX_CONCURRENCY`, default 2. The next request is already queued on the
  server while the previous line downloads, so the GPU does not wait on network
  time. The output keeps the script order. If a line fails, the provider
  cancels the remaining lines.
- **Not included in this version:** the delivery `style_prompt` and non-speech
  tags. Voicebox's `instruct` field and its Chatterbox tags can be added later.

### Errors

The following errors fail the briefing with a readable message:

- The server cannot be reached: "Can't reach Voicebox at <url>."
- The model is not downloaded.
- The voice is not found.
- A line reports status `failed`. The message includes Voicebox's `error`
  text.

A partial audio file is deleted when generation fails, as the other providers
already do.

## Scale and robustness

- **Provider registry.** `app/services/tts/registry.py` is the single source
  of truth for provider IDs, labels, and capabilities (custom voice IDs, voice
  listing, timeout budget). Adding a provider takes a registry entry, a
  provider class, and a Settings card. The cast API returns the provider list,
  so the frontend does not hard-code providers.
- **Indexes and invariants.** Casts get a composite index on
  `(user_id, profile_id, tts_provider)`. A partial unique index on the same
  columns, `WHERE is_default = 1`, makes the database enforce "one default per
  provider", including under concurrent requests. The migration removes
  duplicate defaults before it creates the index. `set_default_cast` flushes
  the unset before it sets the new default.
- **Existing bug.** Today `create_cast` clears the profile's default and does
  not set a new one. The next briefing then quietly creates another Gemini
  "Augustus Daily" cast. This is where the duplicate "Augustus Daily" and
  "Alex and Sam" casts come from. The new "first cast becomes default" rule
  replaces that code.
- **One provider per briefing.** Generation reads the active provider once, at
  cast resolution. Both the cast and the TTS call use that value, so changing
  Settings during a generation cannot mix providers.
- **Timeout budget.** Today every briefing is capped at
  `BRIEFING_TIMEOUT_MINUTES` (15). A 25-minute Voicebox episode (about 300
  lines on one GPU) would exceed that cap. The registry provides a budget per
  provider: Voicebox uses the larger of the global value and
  `VOICEBOX_BRIEFING_TIMEOUT_MINUTES`, which defaults to 60.
- **Voicebox efficiency.**
  - Each briefing uses one pooled HTTP client.
  - Status arrives over server-sent events instead of polling.
  - Audio streams to disk, and stitching streams too.
  - The profile list is cached for 30 s for each server URL, which covers the
    cast editor, the voices API, and synthesis.
  - Voicebox history items are deleted in a `finally` block, so failed and
    cancelled lines are removed too.
- **Security.** The new Voicebox endpoints (models and connection test) take a
  URL and make the server call it. Unlike the older settings endpoints, they
  require a logged-in user. They accept only `http` and `https` URLs, and they
  return parsed fields, never raw response bodies.
- **Observability.** The provider logs the time for each line, the total time,
  and the real-time factor. Error messages include the Voicebox generation ID.

## Testing

- **Part 1 (pytest)**
  - Backfill inference: one case for each rule, plus the fallback.
  - One default per profile and provider.
  - The first cast created for a provider becomes its default.
  - Every row of the cast resolution table: explicit and matching, explicit
    and mismatched (400), implicit and mismatched (fallback), and no default
    (`NoCastForProviderError`).
  - `?provider=all`.
  - The `/api/casts/voices` response for each provider.
- **Part 1 (vitest)**
  - Grouping casts by active provider and building the "other providers"
    section.
  - Voice dropdown options, including the custom-ID entry.
- **Part 2 (pytest).** Use `httpx.MockTransport` in place of a real Voicebox
  server.
  - The generate, poll, download, and delete sequence.
  - Preset engine override and the model table mapping.
  - Matching a voice by ID or by trimmed name.
  - Unknown voice, failed line, and timeout.
  - Cancellation.
  - Stitching a 24 kHz WAV and a 44.1 kHz WAV, with correct segment timings.
- **Manual check.** On the Voicebox server at 192.168.4.44, generate a short
  briefing with a two-host cloned-voice cast, and check the audio, chapters,
  and Voicebox history (no leftover items). Then switch to Gemini and back, and
  check the Casts page and cast pickers.

## Out of scope

- Selecting a provider per cast (casts follow the global provider).
- Creating or editing Voicebox profiles from Augustus.
- Voicebox style instructions, effects chains, and the personality rewrite.
- Voicebox servers behind an authenticating proxy. Augustus sends no
  credentials, which matches a stock Voicebox server.
