# AWS status

Everything a session needs before spending money here. Values verified
2026-08-16 by read-only API call from this machine; re-check with the commands
at the bottom rather than trusting the numbers blind.

## Account

| | |
| --- | --- |
| Account | **842954813809** — Saurabh's own |
| Profile | `antigravity-dev-user` |
| Region | `us-east-1` |
| Secrets | Doppler, project `unfoundbox`, config `dev_personal`, scoped at `~/code` |

**Never `katana` (529738799911) or `katana2` (471112666526).** Those are Sam's
accounts and appear in `~/.aws/credentials` only because other work needs them.
Name the profile explicitly on every command.

`antigravity-dev-user` is deliberately restricted. It can read Service Quotas
and describe instance types, but it is denied `GetAWSDefaultServiceQuota`, and
almost certainly `RequestServiceQuotaIncrease` too. Quota increases need an
admin identity or the console.

## Credits

AWS Activate, **$800**. Two things about it are unverified and load-bearing:

- Which account the credits landed in. Confirm before planning around them.
- Whether Activate covers **Spot** and **Dedicated Hosts**. Neither appears in
  the published exclusion list (Marketplace, Professional Services, Route 53
  registrations), but absence from a list is not confirmation.

## The GPU box — where the credits should go

`g6e.2xlarge` Spot, `us-east-1`, ~**$0.75/hour**, one L40S with 48GB VRAM.
No minimum billing period, so short jobs cost what they cost.

**$800 ≈ 1,066 GPU-hours.** That is a real distillation and post-training
budget, not just generation time. It is the reason the credits belong here
rather than on EC2 Mac.

`infra/gpu-box.sh` defaults to the smaller `g6e.xlarge`; `spacepilot/cli.py` uses
`g6e.2xlarge`. They disagree on purpose — the shell script predates the CLI.

### Quota, and why it bites

| Quota | Code | Value | Meaning |
| --- | --- | --- | --- |
| All G and VT Spot Instance Requests | `L-3819A6DF` | **8 vCPU** | exactly one `g6e.2xlarge` |

Adjustable. 64 vCPU would allow eight concurrent boxes, or one four-GPU
`g6e.12xlarge` plus eval workers.

Quota is permission, not capacity — Spot can still refuse when G6e is tight in
`us-east-1`. The regional fallback is `us-west-2`, which needs its own increase
*and* a change to the hardcoded region in `spacepilot/cli.py`.

At eight boxes the burn is $6/hour: the whole $800 in about **133 hours**.
Raising the quota removes the ceiling, not the meter. Cap `pluto launch` before
there is enough headroom to forget.

## EC2 Mac

Bare-metal Dedicated Hosts, one Mac per host — not VMs. **Every Mac host quota
on this account is currently 0**, so none can be launched without an increase.

Billing is per second with a **24-hour minimum host allocation**, mandated by
the Apple macOS licence. There is no such thing as a cheap short experiment:
every allocation costs a full day whether used for one hour or twenty-four.

| Instance | Chip | Memory | $/hr | 24h minimum | Quota code |
| --- | --- | ---: | ---: | ---: | --- |
| `mac2.metal` | M1 | 16 GiB | 0.65 | **15.60** | `L-5D8DADF5` |
| `mac2-m2.metal` | M2 | 24 GiB | 0.878 | **21.07** | `L-B90B5B66` |
| `mac-m4.metal` | M4 | 24 GiB | — | — | `L-2CBA8B92` |
| `mac2-m2pro.metal` | M2 Pro | 32 GiB | 1.56 | **37.44** | `L-14F120D1` |
| `mac2-m1ultra.metal` | M1 Ultra | 128 GiB | — | — | `L-AE4D744C` |
| `mac-m4pro.metal` | M4 Pro | 48 GiB | 1.97 | **47.28** | `L-6919FC30` |
| `mac-m4max.metal` | M4 Max | 128 GiB | 6.25 | **150.00** | `L-D82CB68A` |
| `mac-m3ultra.metal` | M3 Ultra | 256 GiB | 12.50 | **300.00** | `L-7108A7B5` |
| `mac1.metal` | Intel | 32 GiB | — | — | `L-A8448DC5` |

Dashes are rates not verified from a primary source yet. Mac host quotas count
**hosts**, not vCPUs — request `1`, not `8`.

The M3 Ultra is a 256GB Apple Silicon machine for $300 a day, which makes every
"won't fit in 32GB" limit disappear. It is also 37% of the credit balance for
one day, so treat it as a single fully-scripted run that answers everything at
once, never as an iteration platform.

`CreateMacSystemIntegrityProtectionModificationTask` appears in this account's
quota list, which confirms the SIP-modification API is real and reachable —
selectively disabling debugging, DTrace, or kext-signing restrictions is
possible on EC2 Mac. That is the only reason to prefer it over a Mac on a desk.

Known limits: no microphone input, and **FileVault loses the boot volume's data
on reboot, stop, or terminate**. Instances boot from EBS rather than the
internal SSD, which is why Apple Intelligence does not work there.

### AWS Mac pricing is not the market rate

Do not read $47.28/day and assume that is what a Mac costs. Rates below
verified 2026-08-16; USD/INR 95.66, EUR/USD 1.1575.

**M4 Pro class**

| Provider | Spec | Per month |
| --- | --- | ---: |
| OakHost `M4Pro.L` | M4 Pro 12C/16C, 64GB, 1TB | €245 ex VAT ≈ **$284** |
| MacStadium `M4.L` | M4 Pro 12C, 48GB, 1TB | **$349** |
| Scaleway `M4-XL` | M4 Pro 14C/20C, 64GB, 2TB | €335 ≈ **$388** |
| AWS `mac-m4pro.metal` | M4 Pro 14C/20C, 48GB | **~$1,418** |
| Buy, Apple India | Mac mini M4 Pro base | ₹2,23,900 ≈ $2,340 once |

OakHost is the price leader and gives 64GB where MacStadium gives 48GB, with no
setup fee and monthly cancellation. It also ships a KVM module — remote VNC and
power control that survive a failed boot, which matters on a box you intend to
push into strange states. Its M4 Pro is the 12C/16C bin, same as MacStadium's
and below the 14C/20C part AWS and Scaleway rent.

**Ultra class**

| Provider | Spec | Per month |
| --- | --- | ---: |
| MacStadium `S2.L` | M2 Ultra 24C, 128GB, 2TB | **$449** |
| AWS `mac-m3ultra.metal` | M3 Ultra, 256GB | **~$9,000** |
| Buy, Apple India | Mac Studio M3 Ultra, 96GB | ₹5,99,900 ≈ $6,271 once |

AWS is 5x OakHost on M4 Pro and 20x MacStadium on Ultra. **For a 256GB machine,
renting never makes sense at any duration** — one month of AWS buys the Mac
outright with $2,700 left over. MacStadium's M4 stock is also constrained:
volume orders want an annual contract, three units minimum.

**Ruled out, so nobody re-checks them:**

| Provider | Why not |
| --- | --- |
| RunPod | No macOS or Apple silicon at all. NVIDIA GPU cloud only. |
| Flow Swiss | Lineup stops at M1 Max / M2 Pro. Swiss data sovereignty is the pitch; no M4 or Ultra. |
| MacinCloud | Managed and shared dev desktops, pay-as-you-go. Not bare metal at the tiers that are cheap. |
| GitHub Actions | macOS ARM runners have **14GB RAM** and bill $0.12–0.16/min ≈ $9.60/hr. No 24h minimum, and free on public repos, so viable for a short Core ML placement check — useless for anything that needs memory. |
| Hetzner, Vultr, GCP, Azure, Oracle | No Apple hardware. Listicles that claim otherwise are wrong. |

**No provider anywhere rents an Ultra above M2 Ultra 128GB except AWS.** If the
work needs 256GB of unified memory, the options are AWS at ~$9,000/month or
buying. There is no third answer.

**AWS earns its premium in exactly two places.** First, the
SIP-modification API — MacStadium gives root, AWS gives programmatic control
over DTrace, debugging and kext-signing restrictions, which is what going
below Core ML into private ANE frameworks needs. Second, region adjacency: a
Mac in `us-east-1` sits beside the g6e box with no egress and low latency to
the same buckets, where a MacStadium host is a separate network billed both
ways.

**And credits beat list price.** Three M4 Pro allocations is $142 of Activate
credit against $349/month of real money. Bad value, zero actual cost — so for
a handful of scripted sweeps, use AWS. For anything sustained, MacStadium. For
256GB, buy.

## Re-checking any of this

All read-only, safe to run unprompted:

```bash
aws sts get-caller-identity --profile antigravity-dev-user
```

```bash
aws service-quotas get-service-quota --service-code ec2 --quota-code L-3819A6DF --region us-east-1 --profile antigravity-dev-user
```

```bash
aws ec2 describe-instance-type-offerings --location-type region --region us-east-1 --filters Name=instance-type,Values='mac*' --profile antigravity-dev-user --query 'InstanceTypeOfferings[].InstanceType'
```

Requesting an increase is a mutating call and belongs to Saurabh, not to a
session. The console form is at Service Quotas → EC2 → the quota code above,
and it is also where the justification text goes.
