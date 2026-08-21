#!/usr/bin/env bash
# Review by default; pass --apply only during an approved maintenance change.
set -euo pipefail

PROJECT=${GCLOUD_PROJECT:-familyvault-497322}
INSTANCE=${GCLOUD_INSTANCE:-familyvault}
ZONE=${GCLOUD_ZONE:-us-east1-c}
REGION=${ZONE%-*}
POLICY=${GCLOUD_SNAPSHOT_POLICY:-familyvault-daily}
mode=${1:---dry-run}
[[ "$mode" == --dry-run || "$mode" == --apply ]] || {
  echo "usage: $0 [--dry-run|--apply]" >&2
  exit 2
}

apply() {
  if [ "$mode" == --apply ]; then
    "$@"
  else
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
  fi
}

gcloud compute instances describe "$INSTANCE" --zone "$ZONE" --project "$PROJECT" >/dev/null

for rule in default-allow-ssh default-allow-rdp default-allow-icmp; do
  if gcloud compute firewall-rules describe "$rule" --project "$PROJECT" >/dev/null 2>&1; then
    apply gcloud compute firewall-rules delete "$rule" --project "$PROJECT" --quiet
  fi
done

if ! gcloud compute resource-policies describe "$POLICY" \
  --region "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  apply gcloud compute resource-policies create snapshot-schedule "$POLICY" \
    --project "$PROJECT" --region "$REGION" --daily-schedule \
    --start-time 03:00 --max-retention-days 14 \
    --on-source-disk-delete keep-auto-snapshots
fi

attached=$(gcloud compute disks describe "$INSTANCE" --zone "$ZONE" --project "$PROJECT" \
  --format='value(resourcePolicies.basename())')
if [[ ",$attached," != *",$POLICY,"* ]]; then
  apply gcloud compute disks add-resource-policies "$INSTANCE" \
    --project "$PROJECT" --zone "$ZONE" --resource-policies "$POLICY"
fi

echo "Post-change checks:"
echo "  gcloud compute firewall-rules list --project $PROJECT"
echo "  gcloud compute disks describe $INSTANCE --zone $ZONE --project $PROJECT --format='yaml(resourcePolicies)'"
