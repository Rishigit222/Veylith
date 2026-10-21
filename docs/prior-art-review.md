# Prior-art and platform review

Review date: 2026-10-21

## Findings

| System | What it establishes | Overlap with Chronicle Guard | Narrow experiment boundary |
| --- | --- | --- | --- |
| AgentDojo | A benchmark and simulator for tool-using agents, prompt injection, and utility/security trade-offs. | Adversarial agent workflows and reproducible task environments. | Chronicle Guard tests event-time/processing-time races and approval lifecycle invariants rather than prompt-injection task success alone. |
| Microsoft Agent Governance Toolkit | Governance patterns for agent identity, policy, tool access, and auditability. | Runtime policy and lifecycle governance. | The baseline is intentionally transparent and per-action; the experiment measures an independent transition verifier at the execution boundary. |
| Promptfoo | Evaluation/red-team harnesses for LLM apps, including prompt injection and policy checks. | Scenario generation and regression evaluation. | Chronicle Guard does not claim superior prompt-security coverage; it focuses on stateful temporal counterexamples. |
| Inspect AI | Evaluation framework for agents with structured solvers, tools, and scorers. | Reproducible agent evaluation. | This product keeps the core verifier deterministic and usable without a model API. |
| Runtime verification / temporal logic | Established approach for checking traces against temporal properties such as `G(execute -> approval_valid)`. | Direct conceptual foundation. | The implementation is a bounded explicit state machine, not exhaustive model checking or a formal proof of all workflows. |

## Hypothesis and experiment

Hypothesis: an independent verifier can detect a dangerous transition missed by a simplified per-action baseline when approval is valid during planning but revoked before execution.

Controlled variables: scenario version, seed, initial state, ordered event stream, policy version, and verifier version. The same stream is evaluated three ways:

1. Isolated unsafe simulator behavior (the raw execution event is present).
2. Baseline policy (`baseline-v1`) that checks request/approval/execution presence.
3. Baseline plus Chronicle Guard temporal verification at the execution transition.

Success criterion: the baseline returns `allowed=true` for `revoked_approval_race`, while the temporal verifier returns `valid=false`, identifies the first failing execution event, and a candidate repair produces a valid replay without removing the legitimate happy path.

## Ring resources and limitations

The project reviewed the official Ring developer portal and the hackathon listing. Ring integrations are access-controlled and may require an approved account, application registration, OAuth scopes, and review. No Ring credentials or verified API contract were available in this workspace on 2026-10-21. Therefore the application reports **simulator-only** and does not claim a Ring integration. No physical devices, visitor identities, camera feeds, or live security actions are used.

Sources reviewed:

- Amazon Developer Challenge listing: `https://developer.amazon.com/alexa/alexa-skills-kit/amazon-developer-challenge`
- Ring developer portal: `https://ring.com/developer`
- Ring developer getting started: `https://ring.com/developer/get-started`
- AgentDojo: `https://agentdojo.spylab.ai/`
- Promptfoo: `https://www.promptfoo.dev/`
- Inspect AI: `https://inspect.aisi.org.uk/`
- Agent Governance Toolkit: `https://github.com/microsoft/agent-governance-toolkit`

## Honest conclusion

The implementation demonstrates the targeted divergence against its simplified baseline for the flagship race and duplicate/replay cases. It does not establish superiority over the full security controls of AgentDojo, Promptfoo, Inspect, Microsoft tooling, Ring, or any production authorization system. Those systems solve broader or different problems and should be compared with a shared benchmark before making stronger claims.
