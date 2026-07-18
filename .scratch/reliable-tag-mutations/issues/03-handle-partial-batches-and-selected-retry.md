# 03 — Handle Partial Batches and Selected Retry

Status: ready-for-agent
Category: bug
Priority: high
Blocked by: 02

**What to build:**

For a tag mutation across multiple selected photos, TAGGER must communicate and retain per-photo outcomes. Successful photos become confirmed; failed photos restore Confirmed metadata and remain visibly failed. The `:retry` command must retry only failed mutations belonging to currently selected photos.

- [ ] A multi-photo mutation can represent successful and failed photo writes in one user-visible outcome.
- [ ] Successful photos remain confirmed while only failed photos are restored, marked failed, and eligible for retry.
- [ ] The UI summarizes mixed batch results without hiding per-photo indicators.
- [ ] `:retry` retries failed mutations for selected photos only and never resubmits successful or pending work.
- [ ] Pure coordination and offscreen command-routing tests cover partial success and selected retry.
