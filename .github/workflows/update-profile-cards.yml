name: Update profile cards

on:
  push:
    branches:
      - main
  schedule:
    - cron: "0 */12 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-cards:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Generate profile cards
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_USERNAME: Sss330
          DISPLAY_NAME: Yaroslav
          WAKATIME_API_KEY: ${{ secrets.WAKATIME_API_KEY }}
        run: python3 .github/scripts/generate_profile_cards.py

      - name: Commit updated cards
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add profile/stats.svg profile/top-langs.svg profile/wakatime.svg profile/streak.svg
          git commit -m "Update profile cards" || exit 0
          git push
