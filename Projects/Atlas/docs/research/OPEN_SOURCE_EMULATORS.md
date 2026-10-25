# Open-Source Android Emulators — Phase 0 Research

**Accessed:** 2026-10-25
**Status:** [RESEARCH] — desk research only. Nothing here has been tested on a device. Every launch method below must be confirmed in the Phase 0 launch feasibility spike before it goes into the ATLAS registry.

Labels follow Section 0 of `../CEO_DIRECTIVE.md`. Where a fact could not be confirmed from a primary source it is marked **(verify)**.

---

## 1. Key findings

1. **Open-source emulators cover every Tier 1 system and most of Tier 2.** RetroArch alone covers all of Tier 1 through its cores. Maintained open-source standalone emulators exist for GameCube/Wii, PSP, 3DS, DS, N64, Dreamcast, PS2, arcade and ScummVM.

2. **Most of them accept launches from a frontend.** ES-DE's Android configuration (MIT-licensed (verify), source in §7) has a launch command for every emulator in the table below except Lemuroid and Panda3DS. That is strong evidence that external launching works, but it is not proof for ATLAS: every entry still needs an on-device test.

3. **There are four different launch styles, and they affect decision D2 (storage).**

   | Style | How the game file is passed | Examples |
   |---|---|---|
   | **SAF content URI** | Storage Access Framework URI (in the intent data or an extra) | Dolphin, PPSSPP, Azahar, melonDS, Mupen64Plus, Flycast, ARMSX2, Play!, Snes9x EX+ |
   | **FileProvider content URI** | A URI the frontend creates for a single file | NES.emu, GBA.emu, GBC.emu, MD.emu, PCE.emu and most other Broglia emulators, SkyEmu, Virtual Virtual Boy |
   | **Real file path** | A plain filesystem path | **RetroArch**, NooDS, MAME4droid, ePSXe (proprietary) |
   | **Game ID** | An identifier, not a file | ScummVM, Vita3K |

   **[ANALYSIS] This matters for D1/D2.** RetroArch needs a real file path *and* the path of a core inside RetroArch's own data folder. A pure SAF approach, which is what the Google Play-friendly option gives you, cannot easily provide real paths. RetroArch is the only maintained open-source route to PS1 (finding 4), and the main route for most Tier 1 systems. So "SAF only" likely means no RetroArch, and that in turn means no open-source PS1. ES-DE also notes that FileProvider only works for single files, so multi-file games (`.cue`/`.bin`) need SAF instead.

4. **PS1 has no maintained open-source standalone emulator.**
   - DuckStation stopped being open source in September 2024. It moved to the PolyForm Strict licence, then to CC BY-NC-ND 4.0.
   - In March 2026 its developer said the Android version would get no more updates. The last Android release was around May 2025.
   - ePSXe and FPse are proprietary.
   - That leaves RetroArch cores (or Lemuroid) for open-source PS1. PS1 is in Tier 1, so the Phase 0 spike must cover PS1 through RetroArch.

5. **"Open source" does not mean free for commercial use.** Several popular cores ship under non-commercial licences:
   - Snes9x (also used by Snes9x EX+)
   - Genesis Plus GX
   - PicoDrive (MAME licence with a non-commercial clause)
   - FinalBurn Neo
   - the older MAME-based cores

   **[ANALYSIS]** This only matters if ATLAS bundles or embeds emulator code. Launching a separately installed app does not combine code, so it should create no licence obligation for ATLAS. That conclusion needs legal confirmation (Commercial & Compliance).

6. **Lemuroid is a competitor, not an integration target.** It is GPL-3.0-or-later, built on libretro and open source. ES-DE has no launch rule for it, and nothing found shows it accepts launches from other frontends. It is also the reference example of the alternative strategy in §5.

7. **Some apps are "open source but launch is paywalled or broken" in practice** (per ES-DE):
   - NooDS: the Play Store build can't be launched externally.
   - Yaba Sanshiro 2: only the paid Pro version can be launched externally, and some devices show "Cannot initialize SH2".
   - Panda3DS: no way found to launch a specific game directly.
   - The registry needs a field for this.

---

## 2. Open-source standalone emulators (systems in ATLAS scope)

Launch details are taken from ES-DE's `es_systems.xml` and `es_find_rules.xml` (commit `a529a9d`, accessed 2026-10-25). They are [RESEARCH], not [VERIFIED].

| Emulator | Systems | Licence | Package(s) | Launch method (per ES-DE) | File reference | Notes |
|---|---|---|---|---|---|---|
| **RetroArch** | Multi (via cores) | GPL-3.0-only (F-Droid) | `com.retroarch`, `com.retroarch.aarch64`, `com.retroarch.ra32` | Explicit activity `com.retroarch.browser.retroactivity.RetroActivityFuture`; extras `ROM`, `LIBRETRO` (core `.so` path in RetroArch's internal data), `CONFIGFILE` | Real path | ES-DE: "The RetroArch release from the Google Play store is problematic." |
| **Dolphin** | GameCube, Wii | GPL-2.0-or-later (F-Droid) | `org.dolphinemu.dolphinemu` | Action `MAIN`, category `LEANBACK_LAUNCHER`, extra `AutoStartFile` | SAF URI | Actively released (F-Droid current version 2603a) |
| **PPSSPP** | PSP | GPL-2.0-or-later (F-Droid) | `org.ppsspp.ppsspp`, `org.ppsspp.ppssppgold` (paid build) | Action `VIEW`, category `DEFAULT`, data | SAF URI | ES-DE: user must press *Browse* when granting storage |
| **Azahar** | Nintendo 3DS | GPL-2.0 (Flathub) | `org.azahar_emu.azahar` (also legacy `io.github.lime3ds.android`) | Data URI, clear-task/clear-top flags | SAF URI | Successor to Citra; merged Lime3DS and PabloMK7's fork (announced Oct 2024). Dropped `.3ds` and encrypted-game support. |
| **melonDS (Android port)** | Nintendo DS | GPL-3.0 (upstream GPL-3.0-or-later; port licence from a mirror — verify) | `me.magnum.melonds` | Custom action `me.magnum.melonds.LAUNCH_ROM`, extra `uri` | SAF URI | Community port by Rafael Caetano, not the upstream team |
| **NooDS** | Nintendo DS | GPL-3.0 (verify) | `com.hydra.noods` | Extra `LaunchPath`, clear-task flags | Real path | Play Store build does not allow external launch (ES-DE) |
| **Mupen64Plus AE / M64Plus FZ** | Nintendo 64 | GPL-3.0-or-later (F-Droid, AE) | `org.mupen64plusae.v3.alpha` (AE), `org.mupen64plusae.v3.fzurita` (FZ) | Action `VIEW`, data | SAF URI | Both share the `paulscode.android.mupen64plusae` activity, so likely the same codebase (verify) |
| **Flycast** | Dreamcast, Naomi, Atomiswave | GPL-2.0 (F-Droid request) | `com.flycast.emulator` | Action `VIEW`, data | SAF URI | Fork of reicast |
| **ARMSX2** | PlayStation 2 | GPL-3.0 (PCSX2-derived) | `com.armsx2` (several variants) | Action `VIEW`, data | SAF URI | 1.0 released Oct 2025. Young project; reported slower than NetherSX2 (proprietary). |
| **Play!** | PlayStation 2 | BSD-2-Clause (F-Droid request; repo metadata says "other" — verify) | `com.virtualapplications.play` | Action `VIEW`, data | SAF URI | Uses a built-in high-level BIOS, so **no BIOS file needed**. This fits ATLAS's no-BIOS stance. |
| **MAME4droid 2024 / Current** | Arcade (and many computers) | Likely GPL-2.0 (secondary sources). Old 0.139 builds used the non-commercial MAME licence. (verify) | `com.seleuco.mame4d2024` | Action `VIEW`, extra `cli_params` (`-rompath …`) | Real path | ROM sets must match the MAME version. ES-DE: select the ROM root folder, not a system folder. |
| **ScummVM** | ScummVM games | GPL-2.0-or-later per F-Droid (F-Droid entry is stale at 1.5.0; upstream licence may differ — verify) | `org.scummvm.scummvm` | Action `MAIN`, data injected from a file holding the game ID | Game ID | Launch by game ID, not by file |
| **Broglia "EX" suite**: NES.emu, Snes9x EX+, GBA.emu, GBC.emu, MD.emu, PCE.emu, Saturn.emu, NEO.emu, Swan.emu, NGP.emu, Lynx.emu, 2600.emu, MSX.emu, C64.emu | NES, SNES, GBA, GB/GBC, Mega Drive/SMS/GG, PC Engine, Saturn, Neo Geo, WonderSwan, NGP, Lynx, Atari 2600, MSX, C64 | Mixed per module: framework GPL-3.0; each core keeps its own licence (Snes9x is non-commercial) (verify) | `com.explusalpha.*` (PCE.emu is `com.PceEmu`) | Data only | FileProvider for most; SAF for Snes9x EX+, Saturn.emu, NEO.emu | Source on GitHub (`Rakashazi/emu-ex-plus-alpha`). Several are paid on Google Play despite open source. |
| **SkyEmu** | GB, GBC, GBA, DS | (verify) | `com.sky.SkyEmu` | Action `VIEW`, data, clear-task flags | FileProvider | |
| **Virtual Virtual Boy** | Virtual Boy | (verify) | `com.simongellis.vvb` | Action `VIEW`, data | FileProvider | |
| **Yaba Sanshiro 2** | Saturn | Based on Yabause (GPL-2.0); Android app licence (verify) | `org.devmiyax.yabasanshioro2`, `.pro` | Action `VIEW`, extra `org.uoyabause.android.FileNameUri` | SAF URI | Only the paid Pro version can be launched externally; "Cannot initialize SH2" on some devices (ES-DE) |
| **Panda3DS** | Nintendo 3DS | (verify) | `com.panda3ds.pandroid` | — | — | ES-DE: "no way to run a game directly" |

### No longer open source (do not list as open source)

| Emulator | System | What changed |
|---|---|---|
| **DuckStation** | PS1 | GPL until Sept 2024, then PolyForm Strict, then CC BY-NC-ND 4.0 (no commercial use, no derivatives). Android updates halted (developer statements reported March 2026); last Android release around May 2025. Still launchable (`com.github.stenzek.duckstation`, extras `bootPath`, `resumeState`) but frozen. |

### Proprietary emulators (for contrast; not open source)

DraStic (DS), Redream (Dreamcast), ePSXe and FPse (PS1), NetherSX2 (PS2; derived from the closed-source, discontinued AetherSX2), My Boy! / My OldBoy! and Pizza Boy (GB/GBC/GBA), fMSX / ColEm / MasterGear / iNES / Speccy (FMS emulators), Real3DOPlayer (3DO).

---

## 3. Open-source coverage of ATLAS Tier 1 systems

| Tier 1 system | Open-source standalone | Open-source via RetroArch (core licences — verify) | Risk |
|---|---|---|---|
| NES | NES.emu | Mesen, FCEUmm, Nestopia | Low |
| SNES | Snes9x EX+ (Snes9x core is **non-commercial**) | Snes9x (**non-commercial**), bsnes | Low for launching; matters only if bundling |
| Game Boy / Color | GBC.emu, SkyEmu | Gambatte, SameBoy, mGBA | Low |
| Game Boy Advance | GBA.emu, SkyEmu | mGBA, gpSP | Low |
| Mega Drive / Master System / Game Gear | MD.emu | Genesis Plus GX (**non-commercial**), PicoDrive (**non-commercial**), BlastEm, Gearsystem | Low for launching |
| **PlayStation** | **None maintained** | Beetle PSX, PCSX ReARMed, SwanStation | **High:** depends on RetroArch's real-path launching, or on proprietary/frozen apps |

---

## 4. Out of the current ATLAS system list (for later)

ES-DE also has launch rules for open-source or community emulators covering systems ATLAS does not list yet: Vita3K (PS Vita, GPL-2.0, launched by title ID), Cemu (Wii U, ES-DE calls it experimental), Eden (Switch), Winlator (Windows), EKA2L1 (Symbian/N-Gage), J2ME Loader (Java ME), Ruffle (Flash), OpenBOR. Licences not checked.

---

## 5. Strategic option for the CEO: embedded cores (proposed decision D10)

Lemuroid shows a second model: ATLAS could **run libretro cores inside the app** for some systems instead of launching another app.

| | External launch only | Embedded libretro cores for some systems |
|---|---|---|
| Launch reliability | Depends on each emulator's intent support and storage access | ATLAS controls it end to end |
| Storage (D2) | RetroArch needs real paths | Cores can read files ATLAS already has access to |
| Licensing | No code combined; minimal obligations (legal to confirm) | GPL cores very likely make ATLAS GPL when distributed together; non-commercial cores can't ship in a paid product |
| Store policy | Frontend only | ATLAS becomes an emulator itself |
| Scope | Smaller | Much larger: video, audio, input, save states, shaders |
| Competitive position | Competes with ES-DE, Daijisho, Beacon | Also competes with Lemuroid and RetroArch |

**Recommendation [PROPOSED]:** external launch only for MVP. Revisit embedded cores after release, and only for systems where external launching proves unreliable. This keeps ATLAS a frontend, keeps licensing simple and keeps D5 (monetisation) open.

---

## 6. Recommended Phase 0 spike set

Pick emulators that together exercise all four launch styles and cover the riskiest Tier 1 system:

1. **RetroArch** (aarch64 build, not the Play Store build) with a PS1 core and a SNES core: real path + core path
2. **PPSSPP**: SAF URI via `VIEW`
3. **melonDS**: custom action + URI extra
4. **NES.emu or GBA.emu**: FileProvider URI
5. **Dolphin**: `MAIN` + extras (a stretch goal, as GameCube is Tier 2)

For each, record: package and version, exact intent sent, storage permission state, result, return-to-ATLAS behaviour, and whether multi-file games (`.cue`/`.bin`, `.m3u`) work.

---

## 7. Sources (accessed 2026-10-25)

**Primary**
- ES-DE Android emulator find rules (packages and activities): https://gitlab.com/es-de/emulationstation-de/-/raw/master/resources/systems/android/es_find_rules.xml
- ES-DE Android systems configuration (launch commands): https://gitlab.com/es-de/emulationstation-de/-/raw/master/resources/systems/android/es_systems.xml
- ES-DE Android documentation (FileProvider notes, problem emulators): https://gitlab.com/es-de/emulationstation-de/-/raw/master/ANDROID.md
- F-Droid metadata (licence, source, current version): https://gitlab.com/fdroid/fdroiddata/-/tree/master/metadata — files `com.retroarch.yml`, `com.swordfish.lemuroid.yml`, `org.dolphinemu.dolphinemu.yml`, `org.ppsspp.ppsspp.yml`, `org.mupen64plusae.v3.alpha.yml`, `org.scummvm.scummvm.yml`
- Azahar: https://azahar-emu.org/ and Flathub listing https://flathub.org/en/apps/org.azahar_emu.Azahar
- Vita3K repository: https://github.com/Vita3K/Vita3K
- F-Droid inclusion requests: Flycast https://gitlab.com/fdroid/rfp/-/issues/3522 · Play! https://gitlab.com/fdroid/rfp/-/issues/3525
- FreeBSD PicoDrive licence report: https://bugs.freebsd.org/bugzilla/show_bug.cgi?id=253454

**Secondary**
- DuckStation licence change: https://www.gamingonlinux.com/2024/09/playstation-1-emulator-duckstation-changes-license-for-no-commercial-use-and-no-derivatives/
- DuckStation Android updates ending: https://www.androidauthority.com/duckstation-ends-android-support-3648430/ · https://www.notebookcheck.net/Popular-PlayStation-1-emulator-may-receive-no-further-Android-updates.1249134.0.html · https://www.timeextension.com/news/2026/03/popular-ps1-emulator-duckstation-may-have-reached-the-end-of-the-line-on-android
- ARMSX2: https://www.recalbox.com/blog/2025-11-02-android-emulation-playstation-2-armsx2-retrogaming/ · https://steamdeckhq.com/news/armsx2-a-new-ps2-emulator-for-android-has-officially-released-and-been-open-sourced/
- Azahar merge: https://retrohandhelds.gg/lime3ds-and-pablomk7-citra-fuse-into-azahar/
- melonDS Android port mirror: https://sourceforge.net/projects/melonds-android-port.mirror/
- Play!: https://emulation.gametechwiki.com/index.php/Play!
- MAME4droid licence history: https://f-droid.org/forums/index.html?p=834.html · https://oosmetrics.com/repo/seleuco/MAME4droid-Current
- Broglia EX suite licences: https://f-droid.org/forums/topic/collection-of-classic-video-game-emulators/
- Non-commercial libretro cores: https://docs.libretro.com/development/licenses/ · https://www.libretro.com/?p=828 · https://emulation.gametechwiki.com/index.php/Retron5
- FinalBurn Neo licence: https://wiki.recalbox.com/en/emulators/arcade/final-burn-neo/libretro-fbneo · https://kodi.tv/addons/omega/game.libretro.fbneo
- Vita3K / NooDS: https://www.gamebrew.org/wiki/Noods_Vita

**Not reachable from this session:** the GitHub API and libretro's documentation and GitLab hosts were blocked by the network proxy. Repository licence files and libretro core info files could not be read directly; those items are marked (verify).
