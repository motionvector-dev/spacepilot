#!/usr/bin/env bash
# Launch / inspect / tear down the high-performance AWS Spot build runner.
#
# Configured with:
#   - 10-hour auto-terminate death clock (`shutdown -h +600` on boot)
#   - Spot pricing (~$0.15 - $0.19/hr)
#   - Automatic Tailscale mesh joining with Tailscale SSH (`aws-builder`)
#   - Injected local SSH public key (~/.ssh/id_ed25519.pub)
#   - Instance-initiated shutdown behavior: terminate (EBS deleted on termination)
#
# Usage:
#   ./build-box.sh launch      # create Spot instance, start 10h death clock, connect Tailscale
#   ./build-box.sh status      # show instance state, public IP, and death clock
#   ./build-box.sh ssh         # shell into the instance
#   ./build-box.sh terminate   # destroy immediately before the 10h timer expires
#
set -euo pipefail

PROFILE="${AWS_PROFILE:-default}"
REGION="${AWS_REGION:-us-east-1}"
TYPE="${INSTANCE_TYPE:-c7a.2xlarge}"       # 8 AMD Zen 4 vCPUs, 16 GB RAM (~$0.17/hr spot)
KEY="${KEY_NAME:-pluto-gpu-key-2026-07-26}"
KEY_FILE="${KEY_FILE:-$HOME/.ssh/${KEY}.pem}"
SG="${SECURITY_GROUP:-pluto-gpu-sg}"
DISK_GB="${DISK_GB:-80}"
NAME="mvec-aws-builder"
TAG_KEY="CreatedBy"
TAG_VAL="antigravity-dev-user"

aws_() { aws --profile "$PROFILE" --region "$REGION" "$@"; }
die() { echo "error: $*" >&2; exit 1; }

resolve_ami() {
  local ami
  ami=$(aws_ ec2 describe-images --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query 'reverse(sort_by(Images,&CreationDate))[0].ImageId' --output text)
  [[ -n "$ami" && "$ami" != "None" ]] || die "could not resolve Ubuntu 24.04 LTS AMI"
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

get_ts_authkey() {
  doppler secrets get TS_AUTHKEY --project unfoundbox --config dev_personal --plain 2>/dev/null || true
}

build_user_data() {
  local ts_key
  ts_key=$(get_ts_authkey)
  local pub_key=""
  if [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
    pub_key=$(cat "$HOME/.ssh/id_ed25519.pub")
  fi

  cat <<EOF
#!/usr/bin/env bash
set -ex

# 1. Start 10-hour death clock immediately (600 minutes)
# Combined with --instance-initiated-shutdown-behavior terminate,
# this guarantees the machine destroys itself if forgotten.
shutdown -h +600 "10-hour Spot session limit reached. Auto-terminating." &

# 2. Inject local public SSH key
if [ -n "$pub_key" ]; then
  echo "$pub_key" >> /home/ubuntu/.ssh/authorized_keys
  chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
  chmod 600 /home/ubuntu/.ssh/authorized_keys
fi

# 3. Base build dependencies
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  build-essential \
  pkg-config \
  libssl-dev \
  cmake \
  nasm \
  ffmpeg \
  git \
  clang \
  curl \
  jq \
  htop \
  unzip

# 4. Tailscale setup
if [ -n "$ts_key" ]; then
  curl -fsSL https://tailscale.com/install.sh | sh
  tailscale up --authkey="$ts_key" --ssh --hostname=aws-builder --accept-routes
fi

# 5. Rust toolchain & nextest for ubuntu user
su - ubuntu -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable"
su - ubuntu -c "source \$HOME/.cargo/env && cargo install cargo-nextest --locked"

echo "Provisioning complete."
EOF
}

cmd_launch() {
  local existing; existing=$(running_ids)
  [[ -z "$existing" ]] || die "already have $existing. Use 'status', or 'terminate' first."
  [[ -f "$KEY_FILE" ]] || die "missing private key $KEY_FILE"

  local ami; ami=$(resolve_ami)
  local sg_id; sg_id=$(aws_ ec2 describe-security-groups --group-names "$SG" \
      --query 'SecurityGroups[0].GroupId' --output text)

  echo "AMI      $ami (Ubuntu 24.04 LTS Noble)"
  echo "Type     $TYPE (8 Zen4 vCPUs, 16GB RAM)"
  echo "Disk     ${DISK_GB}GB gp3 (DeleteOnTermination: true)"
  echo "SG       $SG ($sg_id)"
  echo "Timer    10 hours (600m) auto-terminate shutdown"

  local user_data; user_data=$(build_user_data)

  local id
  id=$(aws_ ec2 run-instances \
    --image-id "$ami" \
    --instance-type "$TYPE" \
    --key-name "$KEY" \
    --security-group-ids "$sg_id" \
    --count 1 \
    --instance-market-options '{"MarketType":"spot"}' \
    --instance-initiated-shutdown-behavior terminate \
    --user-data "$user_data" \
    --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${DISK_GB},\"VolumeType\":\"gp3\",\"Throughput\":125,\"Iops\":3000,\"DeleteOnTermination\":true}}]" \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=$TAG_KEY,Value=$TAG_VAL},{Key=ManagedBy,Value=spacepilot},{Key=Purpose,Value=mvec-ci-builder}]" \
      "ResourceType=volume,Tags=[{Key=Name,Value=$NAME},{Key=$TAG_KEY,Value=$TAG_VAL},{Key=ManagedBy,Value=spacepilot}]" \
      "ResourceType=spot-instances-request,Tags=[{Key=Name,Value=$NAME},{Key=$TAG_KEY,Value=$TAG_VAL},{Key=ManagedBy,Value=spacepilot}]" \
    --query 'Instances[0].InstanceId' --output text)

  echo "launched $id — waiting for running state..."
  aws_ ec2 wait instance-running --instance-ids "$id"
  local ip; ip=$(instance_ip "$id")
  echo "ip       $ip"
  echo "waiting for ssh to answer (usually 45-60s)..."
  for _ in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -i "$KEY_FILE" \
         "ubuntu@$ip" true 2>/dev/null; then
      echo "SSH ready:"
      echo "  Direct SSH    : ssh -i $KEY_FILE ubuntu@$ip"
      echo "  Tailscale SSH : ssh ubuntu@aws-builder (once user-data finishes)"
      echo
      echo "NOTE: Instance has a 10-HOUR auto-terminate timer active."
      echo "To destroy manually when done: ./build-box.sh terminate"
      return 0
    fi
    sleep 5
  done
  echo "instance $id is running at $ip. User-data is currently provisioning packages."
}

cmd_status() {
  local ids; ids=$(running_ids)
  if [[ -z "$ids" ]]; then
    echo "No builder instances running (nothing billing)."
  else
    aws_ ec2 describe-instances --instance-ids $ids \
      --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,IP:PublicIpAddress,Since:LaunchTime}' \
      --output table
  fi
}

cmd_ip() {
  local i; i=$(running_ids)
  [[ -n "$i" ]] || die "nothing running"
  instance_ip "$i"
}

cmd_ssh() {
  local ip; ip=$(cmd_ip)
  exec ssh -i "$KEY_FILE" "ubuntu@$ip"
}

cmd_terminate() {
  local ids; ids=$(running_ids)
  [[ -n "$ids" ]] || { echo "nothing to terminate"; return 0; }
  echo "terminating builder: $ids"
  aws_ ec2 terminate-instances --instance-ids $ids --query 'TerminatingInstances[].[InstanceId,CurrentState.Name]' --output text
  aws_ ec2 wait instance-terminated --instance-ids $ids
  local left; left=$(running_ids)
  [[ -z "$left" ]] && echo "confirmed terminated. zero ongoing spend." || die "still present: $left"
}

case "${1:-}" in
  launch) cmd_launch ;;
  status) cmd_status ;;
  ip) cmd_ip ;;
  ssh) cmd_ssh ;;
  terminate) cmd_terminate ;;
  *) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
