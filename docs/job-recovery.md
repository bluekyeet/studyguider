# Background job delivery and recovery

## Current contract

- Scheduled lessons have one attempt per topic/local date, claimed before model
  calls. There is no automatic previous-day catch-up or retry of failed/running
  attempts. This is not exactly-once provider execution or guaranteed completion.
- New scheduled lesson generation carries a private run identity and atomically
  inserts its lesson and completes/links the run in the final persistence
  transaction. Model calls still occur outside that transaction. Existing old
  unlinked runs and legacy callbacks may retain the earlier ambiguity; treat them
  as **outcome unknown**, not safe to retry.
- A timeout, exception, old timestamp or absent lesson ID does not prove the
  provider did not finish. Do not reconcile using query/time similarity alone.
- API shutdown waits only briefly for daemon workers. Shutdown returning is not
  proof that every instance's in-flight model/extraction work has stopped.
- Manual lesson requests are not idempotent. After a lost response, inspect saved
  lessons before retrying; no durable request key currently prevents duplicates.

## Safe extraction recovery

1. Stop every API/worker instance and prevent automatic restarts.
2. Verify the processes/containers have actually terminated, not just that a
   shutdown request was accepted. Record the selected interrupted resource IDs.
3. With background workers still stopped, call `worker.recover_interrupted` from
   an administrative one-off process, supplying only those resource UUIDs.
   Import `worker` directly; do not start the API lifespan or another worker.
4. Record returned count; restart workers and inspect extraction outcomes.

Never requeue active claims online. Current status rows do not provide leases or
fencing; reclaiming while a prior worker runs can race its writes.

## Minimum next implementation

- Implemented: authoritative private scheduled-run identity, atomic lesson/link
  transaction after model calls, and initial claim committed before external work.
  Fault-injection checks exercise insert/link rollback and lost-result handling;
  real process termination/commit-acknowledgement loss remains untested.
- Preserve unknown-outcome runs for explicit reconciliation. Do not blindly retry
  existing unlinked records during migration or startup.
- Test claim races, crash-after-claim, provider response loss and the persistence
  boundary against isolated PostgreSQL data. Assert ambiguous attempts do not
  automatically invoke the provider a second time.
- Add durable idempotency keys before offering safe automatic manual-request
  retries. Leases plus fenced writes are required before online reclamation.

Keep the existing PostgreSQL/in-process workers until independent scaling or
background manual jobs justify a separate queue service. A new broker alone does
not resolve commit ambiguity, idempotency or unsafe recovery.
