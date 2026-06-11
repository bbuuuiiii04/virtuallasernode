# PR-G1 v7 Retune Review Packet

This packet is for operator/image-model review. It does not certify visual correctness from metrics alone.

## Packet contents

- Before contact sheets: `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/before/contact_sheets/`
- After contact sheets: `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/after/contact_sheets/`
- Before records: `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/before/records/`
- After records: `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/after/records/`
- After montage: `artifacts/renderer/pr-g1-shape-authority/v7_retune_review_packet/after_contact_sheet_montage.png`

## Required review set

All 19 PR-G1 selected captures are included, which covers all flagged captures, all secondary captures, the original 3 protected captures, and every status-changed capture.

| group | shape_ref | before status | after status | after contact sheet |
|---|---|---:|---:|---|
| protected | `sh1_21b9e82ef84b930b` | authority | authority | `after/contact_sheets/sh1_21b9e82ef84b930b.png` |
| protected | `sh1_41c84ad2ac1f458e` | authority | authority | `after/contact_sheets/sh1_41c84ad2ac1f458e.png` |
| protected | `sh1_adb58093da473f3e` | authority | authority | `after/contact_sheets/sh1_adb58093da473f3e.png` |
| flagged | `sh1_b92cc7b21e95ce78` | provisional | quarantined | `after/contact_sheets/sh1_b92cc7b21e95ce78.png` |
| flagged | `sh1_5f0125b19c4208c0` | provisional | authority | `after/contact_sheets/sh1_5f0125b19c4208c0.png` |
| flagged | `sh1_39cde94194e37010` | provisional | quarantined | `after/contact_sheets/sh1_39cde94194e37010.png` |
| flagged | `sh1_298397439f5ce2a9` | provisional | provisional | `after/contact_sheets/sh1_298397439f5ce2a9.png` |
| flagged | `sh1_2e3da0a4330792c3` | authority | authority | `after/contact_sheets/sh1_2e3da0a4330792c3.png` |
| flagged | `sh1_e9743d87837d24ad` | authority/core_mask conflict | authority/vector | `after/contact_sheets/sh1_e9743d87837d24ad.png` |
| secondary | `sh1_83b4671ca39044d5` | authority | authority | `after/contact_sheets/sh1_83b4671ca39044d5.png` |
| secondary | `sh1_ca3a93cf551f850e` | provisional | provisional | `after/contact_sheets/sh1_ca3a93cf551f850e.png` |
| secondary | `sh1_91ebda39c0075cac` | provisional | provisional | `after/contact_sheets/sh1_91ebda39c0075cac.png` |
| secondary | `sh1_c26886280d3c7364` | provisional | provisional | `after/contact_sheets/sh1_c26886280d3c7364.png` |
| status context | `sh1_14928e116b6d46fb` | authority | authority | `after/contact_sheets/sh1_14928e116b6d46fb.png` |
| status context | `sh1_2bae89cc023a3c52` | authority | authority | `after/contact_sheets/sh1_2bae89cc023a3c52.png` |
| status context | `sh1_3e98be8e27ea1c58` | provisional | provisional | `after/contact_sheets/sh1_3e98be8e27ea1c58.png` |
| status context | `sh1_542fc5442a80e0dc` | provisional | provisional | `after/contact_sheets/sh1_542fc5442a80e0dc.png` |
| status context | `sh1_6fb79ee6e90df590` | provisional | provisional | `after/contact_sheets/sh1_6fb79ee6e90df590.png` |
| status context | `sh1_d9c0e1383b952508` | authority | authority | `after/contact_sheets/sh1_d9c0e1383b952508.png` |

## Counts

- Extractor before: 9 authority, 10 provisional, 0 quarantined.
- Extractor after: 10 authority, 7 provisional, 2 quarantined.
- Builder before: 8 authority, 10 provisional, 0 quarantined, 1 conflict, 0 missing.
- Builder after: 10 authority, 7 provisional, 2 quarantined, 0 conflicts, 0 missing.
