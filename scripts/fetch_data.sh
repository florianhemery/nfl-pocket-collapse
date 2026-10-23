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
# when data/checksums.sha256 was generated).
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

for f in games.csv players.csv plays.csv pffScoutingData.csv; do
  mv "${WORK}/raw/${f}" "${DATA}/${f}"
done
for n in 1 2 3 4 5 6 7 8; do
  mv "${WORK}/raw/week${n}.csv" "${DATA}/tracking/tracking_week_${n}.csv"
done

(cd "${DATA}" && shasum -a 256 -c checksums.sha256)
echo "data ready in ${DATA}"
