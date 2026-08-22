---
trigger: always_on
---

# Dartz: The Functional Core

## I. Error Handling (Either)

1. **Mandatory Either.** All Domain and Data layer methods that can fail **must** return `Either<Failure, Success>`.
2. **No Throwing.** Throwing exceptions for business errors is **prohibited**. Exceptions are reserved strictly for platform/unexpected crashes.
3. **Strict Folding.** **Reject** unwrapping `Either` with `isLeft()` checks. You **must** use `.fold()` (or `.getOrElse`) to handle both cases explicitly.
4. **Use tasks to handle async code** When writing functions that return a `Future<T>` use dartz `Task` to handle the operation, ex:

```dart
return Task(
              () => _applyDeleteAttendanceOps(
                collections: collections,
                studentPath: _generateStudentDocumentPath(studentId: attendance.studentId),
                summary: attendance,
                dataSource: _dataSource,
                batch: _dataSource.newWriteBatch(),
              ).commit(),
            )
            .attempt()
            .mapLeft((e) => UnknownFailure(innerMessage: 'Error deleting attendance, $e', innerError: e))
            .mapRight((_) => const Nothing())
            .run();
```

## II. Types & Collections

1. **Option vs Null.** **Reject** `Option<T>` for simple absence; use Dart's native `?` (nullable types). **Reserve** `Option<T>` strictly for complex composition chains requiring `.flatMap`.
2. **Immutable Collections.** If using `IList` or `IMap`, they **must** remain immutable. Conversion to standard Dart collections is **restricted** to the boundary (UI layer) only.
3. **Tuple Prohibition.** **Reject** `Tuple` for return types. Define a named `record` or a dedicated class to ensure semantic clarity.
