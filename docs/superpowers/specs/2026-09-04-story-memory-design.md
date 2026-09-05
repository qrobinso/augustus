# Listener-aware story memory

Approved direction: the user accepted the September 4 proposal with “Lets do it”.

## Outcome
New briefings prioritize meaningful developments relative to what the active profile has heard. Persistent stories connect coverage across episodes and topic combinations. Evidence travels with research claims. The existing host research, scheduling, audio providers, and player remain the delivery system.

## Scope
This release ships story memory, update-aware editorial selection, chapter listening coverage, explicit follow/less-of-this preferences, and claim evidence in show notes. Interactive follow-up audio is a subsequent release.

## Data and behavior
- Add tables (created through the existing init_db/create_all startup) instead of changing existing database columns. Story rows belong to user_id + profile_id. Development rows link a story, a completed briefing, a chapter index, a summary, and claim evidence. Old episodes remain playable; no inference of historical listening from the old five-second flag.
- An editorial context contains at most 60 recent stories with up to 5 developments each; followed stories get priority. It is scoped to the exact user/profile, regardless of the current topic combination. Heard means at least 80% unique coverage of the corresponding chapter. Generated-only history is explicitly unconfirmed, never “you heard”.
- Extend the existing editor response with story_key (an existing scoped ID or a new event label), development, and change_type (new/update/unchanged). Validate references, deduplicate selected event keys, and suppress unchanged developments only when already heard. The editor sees dates, prior developments, source evidence, listening state, and explicit preferences. Always apply editorial selection even to one candidate. Do not use the shared article URL cache to infer personal exposure.
- Carry a stable article number in chapter markers so chapter associations do not depend on matching rewritten titles. Invalid/missing associations never count as heard. Store chapter_sources and chapter_stories from these IDs.
- Save developments only for completed generated audio. An empty editorial selection returns a completed text-only “No new developments” result without LLM filler or TTS. Fewer selected stories reduce the duration target proportionally (at least one minute), bounded by the requested duration.
- Capture listening as unioned audio-time intervals from continuous playback. Seeking, buffering, paused time, and track changes must not create coverage. Repeated intervals are idempotent; overlapping ranges count once. Persist ranges separately from resume position, flush periodically and on pause/track end/unmount, and retry failed batches. API validates finite bounded ranges and exact profile ownership. Listened is set at 80% episode coverage; manual listened toggles do not manufacture chapter knowledge.
- Research claims retain supporting source URLs and excerpts only when traceable to retrieved material. Reject invented URLs and mismatched excerpts. Unattributed legacy facts are explicitly unverified, never labeled verified. Hosts can interpret evidence but should label disagreement/uncertainty rather than fabricate balance.
- Follow / less-of-this / normal preference is scoped to a story/profile; skips never change preferences. Show notes present development type, summary, evidence, and preference controls.

## Validation
Use in-memory SQLite, fake network/provider boundaries, frontend unit tests for continuous playback, backend route ownership tests, real pipeline tests with fake synthesis, and a production frontend build. No paid generation or changes to the user's live database are necessary for automated verification.

## Constraints
No new dependencies. Preserve existing untracked backend/scripts and dev.sh. Keep changes on feature/story-memory in this checkout. Do not publish or push. UI never claims automatic fact checking guarantees truth. Semantic event grouping and change classification use the editor model and remain probabilistic.
