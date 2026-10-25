# CEO MASTER DIRECTIVE — PROJECT ATLAS

**Version:** 2.0
**Classification:** Executive Product & Engineering Directive
**Project type:** Premium Android game library frontend and emulator launcher
**Primary platform:** Android tablets (landscape, touch and controller)
**Secondary platforms:** Android gaming handhelds, Android phones
**Post-MVP platforms:** Android TV, foldables, home-screen replacement mode
**Product ambition:** The most polished, reliable and easy-to-set-up emulator frontend on Android, with honest compatibility.

---

## 0. HOW TO READ AND EXECUTE THIS DIRECTIVE

Every statement produced under this directive must carry one of these labels:

| Label | Meaning |
|---|---|
| **[RESEARCH]** | Information gathered from an external source. Must include a link and access date. |
| **[ASSUMPTION]** | A reasonable guess made to keep work moving. Must be listed in the Phase report for CEO review. |
| **[PROPOSED]** | A design or plan not yet built. |
| **[IMPLEMENTED]** | Code that exists in the repository and builds. |
| **[VERIFIED]** | Behaviour that was executed and observed, with evidence attached (log, screenshot, test output, device and version). |

Rules that apply to every role:

1. Never present [PROPOSED] or [IMPLEMENTED] work as [VERIFIED].
2. Never invent package names, intent actions, intent extras, file-path requirements or emulator capabilities. Every emulator claim needs a source (official documentation, published source code, or a recorded on-device test).
3. Every competitor or compatibility claim needs a source link and access date. The emulator landscape changes quickly; undated claims are treated as unverified.
4. Where information is missing, make an explicitly labelled [ASSUMPTION] and keep going. Do not stall.

**Team-size assumption [ASSUMPTION]:** ATLAS is built by a small team (one developer working with AI assistance). The specialist roles below are review lenses that every significant decision passes through, not separate departments producing separate reports. Process must stay proportionate to that.

---

## 1. EXECUTIVE MANDATE

Operate as an elite, multidisciplinary product team commissioned to design, engineer, test, secure and ship a commercially competitive Android emulator frontend.

Deliver a complete, production-quality product: not a proof of concept, not a pretty interface over a fragile backend, and not a long feature list that fails to launch games.

**Benchmark products** (study their strengths, weaknesses, user complaints and gaps; never copy their interfaces, assets, branding or proprietary code):

- ES-DE (EmulationStation Desktop Edition)
- Daijisho
- Beacon Game Launcher
- Pegasus Frontend
- LaunchBox
- RetroArch
- Lemuroid

**The objective:** an Android app that combines the visual quality of a premium console interface, the compatibility of a serious emulation frontend, and the simplicity of a consumer entertainment app. On a tablet with a controller it should feel like a dedicated console.

**Where ATLAS must win** (in this order):

1. **Launch reliability.** If ATLAS says a game will launch, it launches.
2. **Ease of setup and migration.** Users can move over from another frontend without losing their library work.
3. **Tablet experience.** The best large-screen, landscape, touch-plus-controller frontend available.
4. **Transparency.** Users always know what is supported, what is experimental, and why something failed.
5. **Visual quality and performance** with large libraries.

The goal is not the most features. The goal is the strongest complete product.

---

## 2. LEADERSHIP ROLES (REVIEW LENSES)

| Role | Owns | Must review |
|---|---|---|
| **CEO / Product Owner** | Vision, scope, priorities, decisions D1–D10 (Section 4), release approval | Every phase exit gate |
| **CTO** | Stack, architecture, engineering standards, build/CI, technical debt | Any new dependency, module or abstraction. Reject complexity that does not buy user value. |
| **CPO** | Competitive research, personas, requirements, roadmap, accessibility priorities | Every feature: which real user problem does it solve? |
| **Lead Android Engineer** | Kotlin, Compose, lifecycle, coroutines/Flow, Room, Hilt, storage, package visibility, input, large-screen layouts | All Android platform decisions |
| **Lead Emulation Integration Engineer** | Emulator registry, launch profiles, ROM formats, multi-disc, BIOS guidance, launch self-test | Every emulator integration claim |
| **Lead UI/UX Designer** | Tablet-first, controller-first and touch-first interaction; navigation; layouts | Every screen, in both touch and controller use |
| **Lead Graphics & Motion Designer** | Motion, artwork presentation, theme tokens, reduced-motion behaviour | Every animation, for mobile GPU cost |
| **Database & Metadata Engineer** | Schema, migrations, indexing, identification, artwork caching, import/export | Every schema change and data-loss risk |
| **Security & Privacy Engineer** | Permissions, safe parsing, dependency audit, privacy policy | Every permission, network call and parser |
| **QA & Automation Director** | Test strategy, Definition of Done tiers, device matrix, regression reports | Every phase exit gate |
| **Commercial & Compliance Director** | Licensing, store policy, metadata provider terms, trademarks, monetisation | Every dependency licence, provider contract and store-facing change |

---

## 3. PRODUCT VISION

ATLAS turns an Android tablet into a unified game console interface for games the user already legally owns.

The user should be able to:

1. Install ATLAS.
2. Complete a short onboarding.
3. **Import an existing setup** from another frontend, or start fresh.
4. Select game folders.
5. See which installed emulators ATLAS detected, and which of them passed the launch self-test.
6. Scan and organise their library.
7. Match games with artwork and metadata.
8. Browse with touch or a controller.
9. Launch a game in the correct emulator.
10. Return to ATLAS exactly where they left off.
11. Organise favourites, collections and history.

Core library browsing and launching must work fully offline after setup. No account registration is required to use ATLAS. Cloud and online features are optional.

### 3.1 Device priority

| Priority | Device class | Rationale |
|---|---|---|
| **Primary (MVP)** | Android tablets, landscape, with touch and Bluetooth/USB controllers | CEO decision. Large screen shows artwork at its best and has room for rich layouts. Touch and controller must both be first-class. |
| **Secondary (MVP-supported, not primary design target)** | Android gaming handhelds (built-in controls, 16:9-class landscape screens) and phones | The tablet landscape layout should scale down to these with adjustments, not redesigns. [ASSUMPTION — to be validated in Phase 4.] |
| **Post-MVP** | Android TV, foldables, dual-screen handhelds | Each needs dedicated focus and layout work and must not delay the core product. |

**Tablet-specific requirements** that apply throughout this directive:

- Landscape is the primary orientation; portrait must remain usable.
- Layouts adapt to window size classes, not specific devices. Must handle common tablet aspect ratios (for example 16:10, 4:3, 3:2).
- Multi-window and split-screen must not break state or layout.
- Touch is a first-class input, not a fallback: tablets are often used without a controller.
- Keyboard and mouse input must not break navigation (some tablets ship with keyboard covers).
- Tablets are often shared within a household. Multiple user profiles and parental controls are a strong post-MVP candidate.
- Many tablets have microSD slots. Removable storage handling is a core requirement.

---

## 4. DECISIONS REQUIRED IN PHASE 0

These decisions shape the architecture. Phase 0 must research each one, present options with trade-offs and a recommendation, and obtain CEO approval before Phase 1 begins.

| ID | Decision | Why it matters |
|---|---|---|
| **D1** | **Distribution channel:** Google Play, direct download/sideload, or both | Google Play restricts broad storage access (`MANAGE_EXTERNAL_STORAGE`) and broad package visibility (`QUERY_ALL_PACKAGES`). The channel determines the storage strategy (D2) and which emulators can be supported. |
| **D2** | **Storage strategy:** Storage Access Framework (SAF) only, all-files access, or a hybrid | SAF is the privacy-preferred option but can be slow to scan very large libraries and returns content URIs, which some emulators cannot open. Decide from the Phase 0 benchmark and launch spike results, not from assumptions. |
| **D3** | **App mode:** standalone app, home-screen replacement, or both | Recommendation for a tablet-first product: standalone app for MVP; optional home-screen mode post-MVP. Home mode changes startup, Back behaviour and boot handling. |
| **D4** | **Metadata providers:** primary and fallback | Candidate providers have different API terms, rate limits, commercial restrictions and account requirements. A provider that requires a user account must stay optional, because ATLAS requires no registration. |
| **D5** | **Monetisation model:** free, paid, freemium, donation-supported | Affects store policy, licence choices (including GPL obligations) and which features are worth building first. |
| **D6** | **Analytics stance** | Recommendation: no product analytics; opt-in crash reporting only. This resolves the conflict between "product analytics" and "no unnecessary telemetry". |
| **D7** | **Reference devices** | The CEO must list the physical tablets (and any handhelds/phones) available for testing. This list is the real-device test matrix and the basis for performance targets. Include at least one mid-range tablet. |
| **D8** | **Product name and trademark** | "ATLAS" is a provisional name. Run a trademark and store-listing conflict check before brand work in Phase 4. |
| **D9** | **Save data scope** | Recommendation: ATLAS does not manage emulator saves in MVP. Post-MVP, consider backing up known save folders. State the decision clearly to users. |
| **D10** | **External launch only, or embedded emulator cores for some systems** | Embedding libretro cores (the Lemuroid model) gives ATLAS full control of launching but very likely makes ATLAS GPL, rules out non-commercial cores in a paid product, and greatly enlarges scope. Recommendation: external launch only for MVP. See `research/OPEN_SOURCE_EMULATORS.md` §5. |

Phase 0 research input: `research/OPEN_SOURCE_EMULATORS.md` (open-source emulator survey, launch methods, licences). Its key finding for D1/D2: RetroArch needs real file paths, so a SAF-only storage strategy likely excludes RetroArch, and with it the only maintained open-source route to PS1.

---

## 5. SUPPORTED SYSTEMS (TIERED)

Platform definitions (system name, file extensions, folder name aliases, artwork categories, default emulator candidates) must be **data files**, so new systems can be added without an app release.

Supporting a system in ATLAS does not mean a working Android emulator exists for it, or that the emulator accepts external launches. Every system has a status in the verified compatibility matrix: **Supported**, **Experimental** or **Unsupported**, with the reason.

| Tier | Systems | Target |
|---|---|---|
| **Tier 1 — MVP** [PROPOSED, confirm after Phase 0 spike] | NES, SNES, Game Boy, Game Boy Color, Game Boy Advance, Mega Drive/Genesis, Master System, Game Gear, PlayStation | Verified end-to-end launch on reference devices. PlayStation is the riskiest: no maintained open-source standalone emulator exists, so it depends on RetroArch (see research). |
| **Tier 2 — Post-MVP core** | Nintendo 64, Nintendo DS, PSP, PC Engine/TurboGrafx-16, Sega CD, 32X, Saturn, Dreamcast, GameCube, Wii, PlayStation 2, Nintendo 3DS, Atari systems, Neo Geo (non-arcade), WonderSwan | Added as integrations are verified. Several of these depend on emulators that have been discontinued or forked in recent years; verify current, maintained options. |
| **Tier 3 — Experimental** | Arcade (MAME, FinalBurn Neo), ScummVM, DOS | These behave differently and must not block the core: arcade games depend on matching ROM-set versions to the emulator version; ScummVM launches by game ID, not by file; DOS games often need per-game configuration. |

Dual-screen handling for DS and 3DS on tablets (layout options, screen arrangement) is the emulator's responsibility. ATLAS only passes through documented launch options.

---

## 6. EMULATOR INTEGRATION ENGINE

This is the most important engineering component. ATLAS's reputation rests on it.

### 6.1 Integration registry as data

Launch profiles are **versioned, signed data files** that ATLAS can update without an app release. Each profile records:

- Emulator identifier and display name
- Android package name(s), including known forks
- Supported systems and file extensions
- Launch mechanism (intent action, component, extras, data URI) — only where documented or verified
- Path requirement: real file path, content URI, or either
- Required URI permission grants
- Minimum and last-verified emulator version
- Compatibility status: Supported, Experimental, Unsupported
- Known limitations and user-facing explanation
- Source of the information (documentation link, source code reference, or test record) and date verified

Package visibility must use explicit `<queries>` declarations for known packages wherever possible, subject to decision D1.

### 6.2 Engine requirements

- Detect installed compatible emulators and their versions.
- Validate files and formats before launch.
- Grant URI permissions safely and only to the target emulator.
- Translate storage locations correctly when an emulator needs a real file path (subject to D2).
- Allow manual emulator configuration and per-game emulator overrides.
- **Launch self-test:** a one-tap check, run during onboarding and available in settings, that confirms each detected emulator can be launched by ATLAS on this device. Results are shown to the user and stored.
- **Accurate failure reporting:** if a launch fails, show which step failed (emulator missing, permission denied, file unreadable, emulator rejected the request) and what the user can do.
- **Honest manual fallback:** where an emulator does not support reliable third-party launching, say so and give manual steps.
- Detect the user's return from the emulator and restore the exact previous screen and focus.

### 6.3 Ongoing ownership

The emulator landscape changes frequently: projects are discontinued, forked or renamed, and package names change. The registry needs a named owner and a maintenance process after release (see Phase 8). Without it, compatibility will decay within months.

---

## 7. GAME LIBRARY ENGINE

### 7.1 Scanning

- Scan only folders the user has authorised, using the strategy chosen in D2.
- Recursive, incremental and resumable scans that never block the UI.
- Progress reporting with actionable errors.
- Handle removable storage: microSD cards that are removed, swapped or remounted must not corrupt the library. Games on missing storage are shown as unavailable, not deleted.
- Designed for libraries of tens of thousands of files without excessive memory use. Phase 0 must benchmark scanning a 20,000-file test library with each candidate storage strategy on a reference tablet; the scan-time target is set from those measurements.

### 7.2 Game identification

Strategies, in order:

1. Platform from folder name and file extension
2. Normalised filename matching
3. Known game identifiers embedded in files, where formats allow
4. Hash matching against reference databases, subject to their licence terms
5. Approved metadata provider matching (D4)
6. User-assisted manual matching

User corrections are never overwritten automatically.

### 7.3 Multi-file and multi-disc games

Group related files into a single game: `.m3u` playlists, `.cue`/`.bin` sets, multi-track images and compressed disc formats supported by the target emulators. Never show individual disc tracks as separate games.

### 7.4 Import and migration (headline feature)

The biggest barrier to switching frontends is losing years of library curation. ATLAS must import, where the formats are documented or openly readable:

- ES-DE `gamelist.xml` files and downloaded media folders
- Pegasus `metadata.txt` collections
- Daijisho and LaunchBox data, where an exportable or documented format exists
- Existing ROM folder layouts used by common frontends, without requiring the user to reorganise files

Import must be non-destructive: ATLAS reads the source data and never modifies it.

### 7.5 Library management

Users can rename display titles, edit metadata, replace artwork, hide games, favourite, create collections, filter by system, sort by title, release date, last played or date added, rescan selected folders, restore missing artwork, and export/import the full ATLAS library configuration.

---

## 8. METADATA AND ARTWORK

- Use only the providers approved in D4, within their API terms and rate limits.
- Record each provider's licence terms, attribution requirements and commercial restrictions in the legal assessment.
- Support box art, background art, screenshots, logos, descriptions, genre, developer, publisher, release date and player count.
- Image resizing, disk cache, memory cache and retry with backoff.
- Library browsing must work offline with cached artwork.
- Missing metadata always has a graceful fallback (generated title card using system branding colours and the game title).
- Treat all downloaded metadata as untrusted input: size limits, safe parsing, no executable content.

---

## 9. PREMIUM USER INTERFACE (TABLET-FIRST)

The interface must feel like a premium console on a tablet held in landscape or docked with a controller.

### 9.1 Input principles

- **Touch and controller are both first-class.** Every screen must be fully usable with either one alone.
- Controller focus is always visible. Touch interaction hides the focus indicator; controller input brings it back.
- Button prompts match the connected controller type where it can be detected.
- No focus traps; every settings screen is reachable by controller.

### 9.2 Home dashboard (MVP)

- Continue Playing
- Favourites
- Systems
- Recently Added
- Collections
- All Games
- Settings and emulator status

Post-MVP: Recommended From Your Library.

### 9.3 Library views

| View | Purpose |
|---|---|
| **Console carousel** | Large artwork, controller-friendly horizontal browsing |
| **Cover grid** | Responsive grid that uses the full tablet width |
| **Compact list** | High-density view for large libraries |
| **System shelves** | Games grouped by console |

A **performance mode** setting (reduced effects, smaller images, no background video) replaces a separate minimal view.

### 9.4 Tablet layout patterns

- Use the extra width: list-detail layouts where the game list and the selected game's details are visible together.
- Navigation rail rather than bottom navigation in landscape.
- Large, readable typography at typical tablet viewing distance.

### 9.5 Game details page

Title, cover, background, platform, developer, publisher, release year, genre, description, player count where available, assigned emulator with its self-test status, launch button, favourite toggle, play history, personal notes, custom artwork, alternative emulator selection. Graceful fallbacks for every missing field.

### 9.6 Themes

- The theme engine is built on design tokens (colour, typography, shape, motion, elevation) so new themes are cheap to add.
- **Ship two themes in MVP:** Midnight (premium dark) and OLED Black (power-conscious).
- Backlog: Neon Arcade, Classic Console, Glass, Retro CRT. Decide later whether to support user- or community-authored themes; that is a long-term format commitment.
- Custom accent colour, background image, animation intensity and font scaling.
- Respect system accessibility settings, including reduced motion and font size.

---

## 10. CONTROLLER SUPPORT

Controller support is core, not optional.

**Test with:** Xbox controllers, PlayStation controllers, 8BitDo controllers, generic Bluetooth controllers, USB controllers, tablet-specific clip-on controllers where available, and handheld built-in controls (secondary devices).

**Must include:** D-pad and analogue stick navigation, confirm/back, shoulder buttons for category switching, visible focus, custom button mapping (including swapping confirm/back), controller detection, reconnection handling without losing position, and sensible multiple-controller behaviour.

---

## 11. GAMING EXPERIENCE FEATURES

### MVP

- **Continue Playing** with one-press relaunch.
- **Favourites** and **custom collections** (for example: Childhood Favourites, Multiplayer, Games to Finish).
- **Launch history** with timestamps.
- **Playtime tracking (opt-in):** use Android's usage access permission (`PACKAGE_USAGE_STATS`, granted by the user in system settings) to measure how long the emulator was in the foreground after an ATLAS launch. Label it clearly as "time in emulator". Without the permission, show launch history only. Never present an estimate as measured playtime.

### Post-MVP candidates (must not delay the core)

- Recommendations from the user's own library (offline)
- User profiles and parental controls (high value for shared household tablets)
- Home-screen widgets
- Home-screen replacement mode (D3)
- Android TV
- Per-game controller profiles
- Save folder backup (D9)
- Local-network library sync between devices
- Authorised achievement integrations
- User-defined launch shortcuts

---

## 12. PERFORMANCE ENGINEERING

Engineering targets (not achieved claims) on a mid-range reference tablet from D7:

| Metric | Target |
|---|---|
| Warm launch to usable interface | Under 1 second |
| Cold launch to usable interface | Under 3 seconds |
| UI animation | 60 FPS where the display supports it |
| Controller navigation response | Under 100 ms |
| Indexed library search | Under 150 ms |
| Library scan (20,000 files) | Set from Phase 0 benchmark |
| Main-thread blocking | No avoidable long-running work |
| Return from emulator to restored screen | Under 1 second |

Methods: lazy loading, virtualised lists, image caching sized for tablet resolutions, database indexing, background work, startup tracing, Baseline Profiles, memory profiling.

Define the measurement method before claiming a result. Reliability always beats animation.

---

## 13. SOFTWARE ARCHITECTURE

### 13.1 Stack

| Area | Choice |
|---|---|
| Language | Kotlin |
| UI | Jetpack Compose, with Material 3 adaptive layouts for window size classes |
| Architecture | Clean Architecture with MVVM (or a justified alternative) |
| Database | Room |
| Async | Coroutines and Flow |
| Background work | WorkManager where appropriate |
| DI | Hilt |
| Networking | OkHttp / Retrofit, only for metadata |
| Images | Coil |
| Testing | JUnit, AndroidX Test, Compose UI testing |
| Build | Gradle Kotlin DSL, version catalog |

Every additional dependency needs a CTO review: what it provides, its licence, and its maintenance status.

### 13.2 Modules

Start lean and split only when a boundary proves useful:

- `app`
- `core-model` — domain types, no Android dependencies
- `core-data` — Room database, storage access, repositories
- `core-emulator` — registry, launch engine, self-test
- `core-metadata` — providers, identification, artwork cache
- `core-designsystem` — theme tokens and shared components
- `feature-library` — home, library views, game details, collections
- `feature-setup` — onboarding, import, scanner, emulator status
- `feature-settings`

Module boundaries must prevent circular dependencies. Use interfaces for emulator adapters, metadata providers and storage implementations. Do not abstract things that have only one implementation and no expected second one.

---

## 14. SECURITY, LEGALITY AND PRIVACY

ATLAS is a legitimate frontend for games the user already owns.

ATLAS must never: distribute games; supply BIOS files; circumvent DRM; bundle emulator binaries without permission; download ROMs; collect unnecessary personal information; request broader permissions than the chosen storage strategy requires.

Required:

- Licence review of every dependency, and of every emulator integration approach (including GPL obligations if any code is reused or bundled).
- Metadata provider terms reviewed and recorded (D4).
- Permissions and package visibility declarations that comply with the chosen channel (D1).
- Privacy policy and licence notices drafted before release.
- Trademark check of the product name (D8).
- No upload of game files, ever, without explicit informed consent for a specific purpose.
- Safe parsing of every imported file (gamelists, playlists, metadata responses) with size limits and malformed-input handling.

---

## 15. QUALITY ASSURANCE

### 15.1 Tiered Definition of Done

| Tier | Applies to | Required before "done" |
|---|---|---|
| **A — Critical** | Launching, scanning, storage handling, database migrations, import, backup/restore | Implementation; code review; unit and integration tests; real-device verification on the reference tablet; error handling for every listed failure scenario; performance measured; no data loss in migration tests; documentation updated |
| **B — Standard** | User-facing features and screens | Implementation; code review; unit tests for logic; Compose UI test for main path; touch and controller verified; accessibility checked; documentation updated |
| **C — Cosmetic** | Themes, animations, visual polish | Code review; visual check on the reference tablet in both orientations; reduced-motion respected; no performance regression |

### 15.2 Required test scenarios

No games; no emulators; storage permission missing or revoked; microSD card removed or swapped; corrupt files; unsupported formats; missing metadata; slow internet; no internet; 20,000+ files; duplicates; multi-disc games; interrupted scans; app backgrounded; rotation; **split-screen and multi-window**; **window resize**; process death; controller disconnection mid-navigation; **keyboard and mouse input**; emulator uninstalled; emulator updated or replaced by a fork; Android OS upgrade.

Never mark a test as passed unless it was executed and the result was observed. Record device, Android version and emulator version for every real-device result.

---

## 16. DEVELOPMENT PHASES

The order is deliberate: **prove launching first, build a working slice second, polish last.**

### Phase 0 — Research, decisions and launch feasibility

Deliver:

- Competitor comparison (sourced and dated)
- User personas, with tablet users as the primary persona
- Answers and recommendations for decisions D1–D10
- **Launch feasibility spike:** a throwaway Android app, run on a reference tablet, that picks a file and launches it in 3–5 target emulators covering all four launch styles found in research (real file path, SAF URI, FileProvider URI, custom action). Proposed set: RetroArch with a PS1 and a SNES core, PPSSPP, melonDS, NES.emu or GBA.emu, and Dolphin as a stretch goal (`research/OPEN_SOURCE_EMULATORS.md` §6). Record for each: package, mechanism, path vs content URI behaviour, permission grants needed, and result.
- **Storage benchmark:** scan time and memory for a 20,000-file test library with each candidate storage strategy.
- Legal and licensing assessment (dependencies, metadata providers, store policy, trademark)
- MVP definition and confirmed Tier 1 system list
- Architecture proposal
- Risk register
- Prioritised backlog with acceptance criteria

**Exit gate:** CEO approves decisions D1–D10, the spike results and the MVP scope.

### Phase 1 — Vertical slice

Build one thin path end to end with plain Material components: select a folder → scan → identify → show a basic grid → launch one Tier 1 system in two emulators → return to the same place.

Includes: compilable modular project, DI, navigation, Room database with migration tests, CI build and test pipeline, the first emulator registry data file.

**Exit gate:** a clean build installs on the reference tablet and launches real games end to end, with evidence.

### Phase 2 — Library engine at scale

Incremental and resumable scanning, removable storage handling, identification strategies, duplicate and multi-disc grouping, search, sort, filter, **import from other frontends**.

**Exit gate:** reliable scanning and import of a large test library on real devices; scan benchmark meets the target set in Phase 0.

### Phase 3 — Emulator integration breadth

All Tier 1 systems, signed and updatable registry, launch self-test, per-game overrides, failure reporting, manual fallbacks, published compatibility matrix.

**Exit gate:** verified end-to-end launching for every Tier 1 system on the reference devices.

### Phase 4 — Design system and premium interface

Brand identity (after D8), typography, colour tokens, motion system, tablet layouts (landscape and portrait), secondary-device adaptations, home dashboard, carousel, grid, list, shelves, game details, two MVP themes, full controller navigation, accessibility.

**Exit gate:** CEO approves the design; complete primary navigation verified with touch alone and with a controller alone.

### Phase 5 — Library management and metadata

Metadata providers (D4), artwork caching, favourites, collections, history, opt-in playtime, manual editing, backup and restore.

**Exit gate:** stable library management; backup/restore and migrations verified with no data loss.

### Phase 6 — Optimisation and testing

Startup optimisation, Baseline Profiles, large-library benchmarks, controller compatibility, device matrix testing, crash fixes, accessibility audit, security review, regression report.

**Exit gate:** all release blockers resolved; performance targets measured and reported honestly.

### Phase 7 — Release

Signed release build, release notes, user guide, privacy policy, licence notices, install instructions, store assets for the chosen channel, release checklist.

**Exit gate:** CEO signs off on release readiness.

### Phase 8 — Operations (ongoing)

- Named owner for the emulator registry.
- Regular check of emulator releases, forks and discontinuations; registry updates shipped as data.
- Triage process for user-reported launch failures, with a way for users to share their self-test results.
- Dependency and security update cadence.

---

## 17. EXECUTIVE REPORTING

At the end of each phase, report:

- **A. Completed deliverables** — with [IMPLEMENTED] or [VERIFIED] labels
- **B. Evidence** — build output, test results, screenshots, logs, verified launches with device and versions
- **C. Outstanding work**
- **D. Risks** — technical, licensing, compatibility, performance, delivery
- **E. Decisions required** — including any new [ASSUMPTION] that needs approval
- **F. Next phase** — tasks in priority order
- **G. Release confidence** — ready for approval, requires changes, or blocked

Never describe planned functionality as completed functionality.

---

## 18. ENGINEERING RULES

1. Inspect existing code before modifying it; never claim to have inspected something you did not access.
2. Preserve working functionality unless a change is approved.
3. Prefer tested, maintainable solutions over shortcuts.
4. No speculative APIs, invented compatibility claims or fabricated test results.
5. Cite a source and date for every external claim.
6. Clear, consistent naming; document important architecture decisions as short decision records.
7. Keep changes small enough to review and test; meaningful commits.
8. Never silently remove a requested feature; report blockers immediately.
9. Protect user data in every migration; test migrations against real prior schemas.
10. Reproducible builds.
11. Security and privacy are release requirements.
12. Real-device testing beats emulator-only assumptions.
13. Significant scope changes need CEO approval.
14. Always optimise for the finished user experience.

---

## 19. CEO ACCEPTANCE CRITERIA

The project succeeds when:

- A production-quality Android frontend ships, designed first for tablets and usable on the secondary devices.
- It has a distinctive premium visual identity.
- Users can import an existing library from another frontend, and scan and manage new ones.
- Every Tier 1 system launches through verified integrations, and every other system's status is shown honestly.
- Every primary screen works with touch alone and with a controller alone.
- Core browsing and launching work without internet access.
- It performs reliably across the device matrix in D7, with measured results.
- Critical (Tier A) functionality is covered by automated and real-device tests.
- User data is protected and never lost in migrations.
- The emulator registry can be updated without an app release, and has an owner.
- Documentation and release assets are complete.

A beautiful prototype alone does not meet these criteria. A working backend with a poor interface does not meet them. A feature-rich app that fails to launch games does not meet them.

---

## 20. IMMEDIATE INSTRUCTION

Do not write production code yet.

1. Complete every Phase 0 deliverable in Section 16, including the launch feasibility spike and the storage benchmark.
2. Present options and a recommendation for each decision D1–D9.
3. Present the Phase 0 executive report in the Section 17 format.
4. Then provide a detailed plan for Phase 1 (the vertical slice).

Do not start all features at once. Do not add frameworks or dependencies the plan does not need.

Build this as if the company's reputation depends on it: exceptional engineering, exceptional design, honest reporting and disciplined execution.

---

## APPENDIX — CHANGES FROM VERSION 1

| Area | Change |
|---|---|
| Phase order | Launch feasibility moved into Phase 0; a vertical slice now comes before the design system; emulator integration moved from Phase 4 to Phase 3 and proven in Phase 1. |
| Primary device | Tablets are now the primary design target; handhelds and phones are secondary; TV and foldables are post-MVP. Tablet-specific requirements added. |
| Decisions | Ten explicit Phase 0 decisions added (distribution, storage, app mode, metadata, monetisation, analytics, devices, name, saves, embedded cores). |
| Migration | Importing from other frontends is now a headline feature. |
| Emulator registry | Profiles are versioned, signed data with a launch self-test and an ongoing owner (new Phase 8). |
| Systems | Split into three tiers; arcade, ScummVM and DOS marked experimental. |
| Metadata | Provider choice and terms are now a Phase 0 decision. |
| Contradictions resolved | Analytics vs telemetry (D6); playtime measurement method specified (opt-in usage access). |
| Scope | Two themes at MVP instead of six; recommendations moved post-MVP; minimal view replaced by a performance mode setting; module list trimmed to start lean. |
| Process | Roles are review lenses for a small team; Definition of Done is tiered; all claims need labels and dated sources. |
