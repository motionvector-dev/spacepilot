#!/usr/bin/env bash
# Launch / inspect / tear down the research GPU box.
#
# Everything runs as antigravity-dev-user, which holds EC2 plus a scoped S3
# prefix and nothing else. The admin profile is never used.
#
#   ./gpu-box.sh launch      # create, wait for SSH, print the IP
#   ./gpu-box.sh status      # what is running and what it has cost so far
#   ./gpu-box.sh ssh         # shell in
#   ./gpu-box.sh bootstrap   # install the upscaler stack on the box
#   ./gpu-box.sh terminate   # destroy it, then verify it is gone
#
# The box bills by the second while it exists. `terminate` is not optional.
set -euo pipefail

PROFILE="${AWS_PROFILE:-default}"
REGION="${AWS_REGION:-us-east-1}"
TYPE="${INSTANCE_TYPE:-g6e.xlarge}"        # L40S, matching modal_app.py's gpu="L40S"
KEY="${KEY_NAME:-pluto-gpu-key-2026-07-26}"
KEY_FILE="${KEY_FILE:-$HOME/.ssh/${KEY}.pem}"
SG="${SECURITY_GROUP:-pluto-gpu-sg}"
DISK_GB="${DISK_GB:-200}"
NAME="pluto-gpu-research"
TAG_KEY=CreatedBy
TAG_VAL=antigravity-dev-user               # the $100/mo budget filters on this exact tag

aws_() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
die() { echo "error: $*" >&2; exit 1; }

# The DLAMI with PyTorch preinstalled. NOT a Marketplace image: those carry
# hourly software fees that promotional credits do not cover, which would put
# real money on the card. Amazon-owned DLAMIs are free.
resolve_ami() {
  local ami
  ami=$(aws_ ssm get-parameter \
    --name /aws/service/deeplearning/ami/x86_64/oss-nvidia-driver-gpu-pytorch-2.7-ubuntu-22.04/latest/ami-id \
    --query 'Parameter.Value' --output text 2>/dev/null || true)
  if [[ -z "$ami" || "$ami" == "None" ]]; then
    ami=$(aws_ ec2 describe-images --owners amazon \
      --filters "Name=name,Values=Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.7 (Ubuntu 22.04)*" \
                "Name=state,Values=available" \
      --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
  fi
  [[ -n "$ami" && "$ami" != "None" ]] || die "could not resolve a PyTorch DLAMI"
  echo "$ami"
}

running_ids() {
  aws_ ec2 describe-instances \
    --filters "Name=tag:Name,Values=$NAME" \
              "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].InstanceId' --output text
}

instance_ip() {
  aws_ ec2 describe-instances --instance-ids "$1" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
}

cmd_launch() {
  local existing; existing=$(running_ids)
  # Refusing here is the whole point: a forgotten box is the only way this
  # experiment quietly costs real money.
  [[ -z "$existing" ]] || die "already have $existing. Use 'status', or 'terminate' first."
  [[ -f "$KEY_FILE" ]] || die "missing private key $KEY_FILE"

  local ami; ami=$(resolve_ami)
  local sg_id; sg_id=$(aws_ ec2 describe-security-groups --group-names "$SG" \
      --query 'SecurityGroups[0].GroupId' --output text)
  echo "AMI      $ami"
  echo "type     $TYPE   disk ${DISK_GB}GB gp3"
  echo "sg       $SG ($sg_id)"

  local id
  id=$(aws_ ec2 run-instances \
    --image-id "$ami" --instance-type "$TYPE" --key-name "$KEY" \
    --security-group-ids "$sg_id" --count 1 \
    --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${DISK_GB},\"VolumeType\":\"gp3\",\"Throughput\":500,\"DeleteOnTermination\":true}}]" \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=$TAG_KEY,Value=$TAG_VAL},{Key=Purpose,Value=upscaler-quality-research}]" \
      "ResourceType=volume,Tags=[{Key=Name,Value=$NAME},{Key=$TAG_KEY,Value=$TAG_VAL}]" \
    --query 'Instances[0].InstanceId' --output text)
  echo "launched $id — waiting for it to run..."
  aws_ ec2 wait instance-running --instance-ids "$id"
  local ip; ip=$(instance_ip "$id")
  echo "ip       $ip"
  echo "waiting for ssh (usually 60-90s)..."
  for _ in $(seq 1 40); do
    if ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -i "$KEY_FILE" \
         "ubuntu@$ip" true 2>/dev/null; then
      echo "ready:   ssh -i $KEY_FILE ubuntu@$ip"
      echo
      echo "REMEMBER: ./gpu-box.sh terminate when done. It bills while it exists."
      return 0
    fi
    sleep 10
  done
  die "instance $id is up at $ip but SSH never answered. Check that $SG allows 22 from your current IP."
}

cmd_status() {
  local ids; ids=$(running_ids)
  if [[ -z "$ids" ]]; then echo "no instances (nothing billing)"; else
    aws_ ec2 describe-instances --instance-ids $ids \
      --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,IP:PublicIpAddress,Since:LaunchTime}' \
      --output table
  fi
  echo "month-to-date spend:"
  aws_ ce get-cost-and-usage --time-period "Start=$(date -u +%Y-%m-01),End=$(date -u -v+1d +%Y-%m-%d)" \
    --granularity MONTHLY --metrics NetUnblendedCost \
    --query 'ResultsByTime[0].Total.NetUnblendedCost.Amount' --output text 2>/dev/null \
    | awk '{printf "  $%.2f net (after credits)\n", $1}' || echo "  (cost explorer unavailable)"
}

cmd_ip()   { local i; i=$(running_ids); [[ -n "$i" ]] || die "nothing running"; instance_ip "$i"; }
cmd_ssh()  { exec ssh -i "$KEY_FILE" "ubuntu@$(cmd_ip)"; }

cmd_bootstrap() {
  local ip; ip=$(cmd_ip)
  local here; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  scp -i "$KEY_FILE" "$here/bootstrap-upscaler.sh" "ubuntu@$ip:~/" >/dev/null
  ssh -i "$KEY_FILE" "ubuntu@$ip" "chmod +x bootstrap-upscaler.sh && ./bootstrap-upscaler.sh"
}

cmd_terminate() {
  local ids; ids=$(running_ids)
  [[ -n "$ids" ]] || { echo "nothing to terminate"; return 0; }
  echo "terminating: $ids"
  aws_ ec2 terminate-instances --instance-ids $ids --query 'TerminatingInstances[].[InstanceId,CurrentState.Name]' --output text
  aws_ ec2 wait instance-terminated --instance-ids $ids
  # Verify rather than trust: a half-failed terminate keeps billing.
  local left; left=$(running_ids)
  [[ -z "$left" ]] && echo "confirmed gone. nothing billing." || die "still present: $left"
}

case "${1:-}" in
  launch) cmd_launch ;;
  status) cmd_status ;;
  ip) cmd_ip ;;
  ssh) cmd_ssh ;;
  bootstrap) cmd_bootstrap ;;
  terminate) cmd_terminate ;;
  *) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
