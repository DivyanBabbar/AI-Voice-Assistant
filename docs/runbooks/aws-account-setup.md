# AWS Account Setup Runbook

**Audience:** Anyone setting up the hindi-voice-ai AWS account from scratch.
**Time required:** ~45 minutes.
**Prerequisites:** You have signed up for an AWS account and the free tier is active.
**Region:** ap-south-1 (Mumbai) unless noted.

> **Warning:** Every step in Part 1 requires root login. After Part 1 you must never log
> in as root again. Treat root credentials like a nuclear launch code.

---

## Part 1 — Root-Only Tasks (do these once, never repeat)

### Step 1 — Lock down root with MFA

1. Sign in to the AWS Console at https://console.aws.amazon.com as root
   (email + root password).
2. Click your account name (top-right) → **Security credentials**.
3. Scroll to **Multi-factor authentication (MFA)** → **Assign MFA device**.
4. Choose **Authenticator app** → follow the QR-code pairing flow with your
   authenticator app (Google Authenticator, Authy, 1Password TOTP, etc.).
5. Enter two consecutive OTP codes to confirm the device.
6. Verify: the MFA section now shows one active device.

### Step 2 — Set a strong root password and lock it away

1. Still in **Security credentials** → **Password** → **Change password**.
2. Generate a 40-character random password (use a password manager).
3. Store it in your password manager under "AWS root — hindi-voice-ai".
4. Do **not** store it anywhere else. Do **not** put it in any code, config, or doc.

### Step 3 — Enable IAM Identity Center (SSO)

IAM Identity Center is free. It lets you create a human identity once and assign it
to AWS accounts with scoped permissions — no long-lived IAM access keys.

1. Go to **IAM Identity Center** (search the services bar).
2. If this is a standalone account (not AWS Organizations), choose
   **Enable** → **Enable with AWS Organizations** — AWS will create a single-account
   org for you automatically. This is required for Identity Center.
3. Wait ~60 seconds for the org and Identity Center instance to provision.
4. Confirm the instance region is **ap-south-1**. If the console defaults to a different
   region, switch regions using the top-right drop-down before enabling.

### Step 4 — Create Permission Sets

Permission sets define what a user can do in an AWS account.

#### AdministratorAccess

1. In Identity Center → **Permission sets** → **Create permission set**.
2. Choose **Predefined permission set** → **AdministratorAccess**.
3. Session duration: **8 hours** (default is fine).
4. Name: `AdministratorAccess` (keep the default name — scripts rely on it).
5. Create.

#### ReadOnlyAccess

1. **Create permission set** again.
2. Choose **Predefined permission set** → **ReadOnlyAccess**.
3. Session duration: **8 hours**.
4. Name: `ReadOnlyAccess`.
5. Create.

### Step 5 — Create your admin user in Identity Center

1. Identity Center → **Users** → **Add user**.
2. Fill in:
   - **Username:** your-name (e.g. `arnav`)
   - **Email:** your work email
   - **First name / Last name:** your name
3. Choose **Send an email OTP** (AWS will email you a one-time link to set your password).
4. Create the user.
5. Check your inbox and follow the link to set a password.

### Step 6 — Assign AdministratorAccess to your user

1. Identity Center → **AWS accounts** → select your account (the only one listed).
2. **Assign users or groups**.
3. Select the user you just created → Next.
4. Select the **AdministratorAccess** permission set → Next → Submit.

### Step 7 — Bookmark your SSO start URL and never use root again

1. Identity Center → **Dashboard** → copy the **AWS access portal URL**
   (looks like `https://d-xxxxxxxxxx.awsapps.com/start`).
2. Bookmark it. This is how you log in from now on.
3. Log out of the root session.
4. Log back in via the SSO portal → select your account → AdministratorAccess.
5. Verify: you see the AWS Console and the top-right shows your SSO user, not root.

**From this point forward, root credentials stay in the password manager. Never use them
for day-to-day work.**

---

## Part 2 — Cost Controls (SSO admin session)

### Step 8 — Enable Cost Explorer

Cost Explorer is free. Without it, you cannot see per-service spend.

1. AWS Console → **Billing and Cost Management** → **Cost Explorer**.
2. Click **Enable Cost Explorer**. It takes up to 24 hours to populate data.
3. Confirm: the Cost Explorer dashboard loads (it may be empty on day one — that is normal).

### Step 9 — Create a $1 actual-spend Budget alarm

This triggers an email the moment you spend a single dollar.

1. **Billing** → **Budgets** → **Create budget**.
2. Choose **Use a template (simplified)** → **Zero spend budget**.
   - Actually, choose **Monthly cost budget** for more control:
3. Template: **Monthly cost budget**.
4. **Budget name:** `monthly-actual-1usd`
5. **Budgeted amount:** `1.00`
6. **Budget type:** Cost
7. **Threshold type:** Actual (not forecasted)
8. **Alert threshold:** 100% of budgeted amount = $1.00
9. **Email recipients:** your email address
10. Create budget.

### Step 10 — Create a $5 forecasted-spend Budget alarm

This triggers if AWS projects you will overshoot $5 by end of month — giving early warning.

1. **Budgets** → **Create budget** → **Monthly cost budget**.
2. **Budget name:** `monthly-forecasted-5usd`
3. **Budgeted amount:** `5.00`
4. **Budget type:** Cost
5. **Threshold type:** Forecasted
6. **Alert threshold:** 100% of budgeted amount = $5.00
7. **Email recipients:** your email address
8. Create budget.

---

## Part 3 — Reduce Bill Surface (optional but recommended)

These services are enabled by default and can generate unexpected charges if a
resource is accidentally provisioned. Disable or audit each region you do NOT use.

| Service | Action |
|---------|--------|
| EC2 default VPCs | Leave as-is (harmless until you launch instances). |
| CloudTrail | A single-region trail on free tier is fine. Do NOT create a multi-region or management-events trail unless needed — those cost money. |
| AWS Config | Do NOT enable. Config rules can cost $2/rule/month. Skip until explicitly needed. |
| GuardDuty | Free 30-day trial, then ~$4/month. Do NOT enable yet. |
| Security Hub | Paid. Do NOT enable yet. |
| Inspector | Paid. Do NOT enable yet. |

**Summary:** Leave everything at defaults. Only provision what a step in this runbook
or a session prompt explicitly asks for.

---

## Part 4 — Configure AWS CLI SSO Locally

After the console setup above, do this on your laptop to wire the CLI.

```bash
# Install AWS CLI v2 if not already present
# macOS: brew install awscli
# Verify
aws --version  # should print aws-cli/2.x.x

# Configure an SSO profile named "admin"
aws configure sso
# Prompts:
#   SSO start URL: https://d-xxxxxxxxxx.awsapps.com/start  (your portal URL from Step 7)
#   SSO region:    ap-south-1
#   SSO account:   (select your account from the list)
#   SSO role:      AdministratorAccess
#   CLI default region:  ap-south-1
#   CLI default output:  json
#   Profile name:  admin

# Log in (opens browser)
aws sso login --profile admin

# Verify
aws sts get-caller-identity --profile admin
# Expected output: your SSO user's assumed-role ARN, not root
```

Add `export AWS_PROFILE=admin` to your `~/.zshrc` (or `~/.bashrc`) so every terminal
session uses this profile by default.

---

## Acceptance Checklist

Before marking this runbook complete, confirm every item:

- [ ] Root MFA device is active (visible in IAM → Security credentials).
- [ ] Root password is stored in password manager and not used for CLI.
- [ ] IAM Identity Center is enabled in ap-south-1.
- [ ] Permission sets `AdministratorAccess` and `ReadOnlyAccess` exist.
- [ ] An Identity Center user exists and has `AdministratorAccess` assigned.
- [ ] SSO portal URL is bookmarked.
- [ ] `aws sts get-caller-identity --profile admin` returns a non-root ARN.
- [ ] Cost Explorer is enabled.
- [ ] Budget `monthly-actual-1usd` ($1 actual) exists with email alert.
- [ ] Budget `monthly-forecasted-5usd` ($5 forecasted) exists with email alert.
- [ ] `scripts/aws-bootstrap.sh` ran successfully and printed a GitHub Actions role ARN.
- [ ] `terraform plan` in `infra/terraform/bootstrap/` shows ~3 resources to create.
