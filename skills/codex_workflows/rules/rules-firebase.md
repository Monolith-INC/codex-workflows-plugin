# Firebase: The Data Stricture

**Codex Anchor**: `[[Knowledge/Firebase_Implementation]]`
*Read the anchor above during Planning Phase for standards on undefined properties, date bucketing (Brazil Rule), and Node.js SDK fixes.*

## I. Firestore (Data Integrity)

### Typing & serialization

1. **Strict Typing.** Reject `Map<String, dynamic>`. All Firestore interactions must use `.withConverter` to serialize/deserialize strongly typed domain objects.
2. **Null Safety.** Database models must strictly handle nullable fields. Missing fields in the DB must default safely or throw explicit schema errors.

### Querying

1. **Index Efficiency.** Queries requiring composite indexes must be defined in `firestore.indexes.json` before implementation.
2. **Read Cost Awareness.** Reject client-side filtering. Filter logic must happen at the query level or strictly in a Cloud Function.
3. **Limiters.** Mandatory `.limit()` on all list queries to prevent unbounded reads.

## II. Cloud Functions (Backend Interop)

### Idempotency

1. **Idempotent Triggers.** All background triggers (onCreate, onUpdate) must be idempotent. They must handle redelivery without corrupting state.
2. **Atomic Batches.** Multi-document updates must occur within a `WriteBatch` or `Transaction`. Partial failures are prohibited.

## III. Security & Optimization

### Rules

1. **Testable Security.** Security rules must be written as code with corresponding unit tests.
2. **Scope Minimization.** Reject wildcard access (`allow read, write: if true;`). Access must be granular per collection and user role.

### Connections

1. **Offline Persistence.** Explicitly configure offline persistence strategies. The app must function (or degrade gracefully) without network.
2. **Emulators.** Local development must strictly use the Firebase Emulator Suite. Production credentials are prohibited in the development environment.
