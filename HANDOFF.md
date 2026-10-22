# Handoff checklist: moving the repo to the league

Goal: the league owns the project (not one person's account), and both the commissioner and the current maintainer
have full access.

## 1. Create the league's GitHub organization (free), done by Danielbirch680
- [ ] github.com → your avatar → **Your organizations → New organization → Free**. Name it `sbffc` (or the closest available
      name). Contact email: the league's email.
- [ ] **People → Invite member →** Brian Harwood's GitHub username (he creates a free account first) → role **Owner**.
- [ ] Brian accepts the invite from his email or github.com/orgs/sbffc/invitation.
- [ ] Optional: add a third owner as a backup so the league is never locked out.

## 2. Transfer the repo
- [ ] Repo `Danielbirch680/sbffc-leaderboard` → **Settings → General → Danger Zone → Transfer ownership →** `sbffc` →
      type the repo name to confirm.
- [ ] Issues, history and Actions move with it. GitHub redirects the old **repo** links, but **not** the old Pages address
      (`danielbirch680.github.io/sbffc-leaderboard` stops working). Plan the switch before the season, or set up the
      custom domain first (step 4) so the public address never changes.

## 3. Turn on Pages from GitHub Actions (repo owner, one time)
- [ ] Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**. (The old setting, "Deploy from a branch
      / main / root", must be switched; the workflow publishes the built site itself.)
- [ ] **Settings → Actions → General:** "Allow all actions" (the default) and keep workflow permissions at the default.
- [ ] **Actions** tab → if it asks, click **"I understand my workflows, go ahead and enable them"**.
- [ ] **Actions → Update SBFFC leaderboard → Run workflow.** Wait for both jobs (build, deploy) to go green.
- [ ] Open the new address, `https://sbffc.github.io/sbffc-leaderboard/` (org name + repo name), and confirm the page loads.
- [ ] Edit `config/season.json` → `"public_url"` to the new address (or the custom domain) → commit.

## 4. Optional: custom domain `leaderboard.sbffc.com`
- [ ] DNS for sbffc.com: CNAME `leaderboard` → `sbffc.github.io`.
- [ ] Org **Settings → Pages → Add a domain** to verify `sbffc.com` (this stops anyone else from claiming it on GitHub).
- [ ] Repo **Settings → Pages → Custom domain** → `leaderboard.sbffc.com` → Save → **Enforce HTTPS**.
- [ ] `config/season.json` → `"public_url": "https://leaderboard.sbffc.com/"`.

## 5. Squarespace
- [ ] Confirm sbffc.com's plan. The embedded leaderboard (Code Block with JavaScript) needs **Core, Plus or Advanced**. On Basic, link to the page instead.
- [ ] Paste `<page address>/squarespace-code-block.txt` into a Code Block (see COMMISSIONER_GUIDE.md).

## 6. Season decisions for the commissioner
- [ ] Sleeper's API terms say "non-commercial use". Confirm with Sleeper, since the league collects entry fees.
- [ ] Tiebreaks: a tied division playoff game (currently the higher seed advances) and tied championship totals (currently shared rank).
- [ ] Fill in the 23 league IDs, set `sample_mode` to false (COMMISSIONER_GUIDE.md → "Each season").
- [ ] Who keeps maintaining the code (contact for the "If it breaks" section): ____________________

## Alternatives (if an organization isn't wanted)
- **Add Brian as a collaborator:** repo **Settings → Collaborators → Add people**. It stays on Danielbirch680's account.
- **Transfer straight to Brian's account:** same as step 2, but to his username. The address becomes `<his-username>.github.io/sbffc-leaderboard`.
