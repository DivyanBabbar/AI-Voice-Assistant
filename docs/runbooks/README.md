# Runbooks

Operational runbooks for the hindi-voice-ai platform. Each runbook covers one failure
mode or operational procedure in enough detail for an on-call engineer to execute it
under pressure.

## Index

| Runbook | Covers |
|---------|--------|
| *(none yet)* | Runbooks will be added as each subsystem is built. |

## How to write a runbook

1. **Title**: `RNNNN-<short-slug>.md` (e.g. `R0001-exotel-call-drop.md`).
2. **Sections**: Symptoms → Impact → Investigation steps → Mitigation → Resolution →
   Prevention → Escalation path.
3. Keep steps concrete and numbered — no prose paragraphs during an incident.
4. Link to relevant dashboards, alert definitions, and ADRs.
5. Review after every incident and update if the runbook was incorrect or incomplete.

## On-call principles

- Mitigate first, investigate second.
- Every page that doesn't have a runbook becomes a new runbook after the incident.
- All production changes during an incident go through the standard PR flow unless
  `main` is blocked and the service is completely down.
