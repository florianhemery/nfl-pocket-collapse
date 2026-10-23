#!/usr/bin/env bash
# Download the NFL Big Data Bowl 2023 files from Kaggle into data/ and verify them.
#
# Prerequisites:
#   - the kaggle CLI (pip install kaggle) with credentials in ~/.kaggle/kaggle.json
#   - the competition rules accepted on the Kaggle website, with your own account
#     https://www.kaggle.com/competitions/nfl-big-data-bowl-2023/rules
#
# Tracking files are renamed week1.csv .. week8.csv -> data/tracking/tracking_week_N.csv.
# Checksums exist only for the four metadata files (the tracking files were not available
# when data/checksums.sha256 was generated): those four are verified, in the temporary
# directory and before anything is moved into data/. The 8 tracking files are NOT verified.
# Uses sha256sum, or shasum -a 256 when sha256sum is missing (macOS).
set -euo pipefail

COMPETITION="nfl-big-data-bowl-2023"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${ROOT}/data"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "error: the kaggle CLI is not installed (pip install kaggle)" >&2
  exit 2
fi

mkdir -p "${DATA}/tracking"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

kaggle competitions download -c "${COMPETITION}" -p "${WORK}"
unzip -q -o "${WORK}/${COMPETITION}.zip" -d "${WORK}/raw"

# Verify the four metadata files where they were extracted, before anything in data/ is
# touched: a mismatch must leave the files already in data/ as they were.
if command -v sha256sum >/dev/null 2>&1; then
  check=(sha256sum -c)
elif command -v shasum >/dev/null 2>&1; then
  check=(shasum -a 256 -c)
else
  echo "error: neither sha256sum nor shasum is installed" >&2
  exit 2
fi
(cd "${WORK}/raw" && "${check[@]}" "${DATA}/checksums.sha256")

for f in games.csv players.csv plays.csv pffScoutingData.csv; do
  mv "${WORK}/raw/${f}" "${DATA}/${f}"
done
for n in 1 2 3 4 5 6 7 8; do
  mv "${WORK}/raw/week${n}.csv" "${DATA}/tracking/tracking_week_${n}.csv"
done

echo "data ready in ${DATA}"
echo "warning: the 8 tracking files have no checksum and were not verified" >&2
