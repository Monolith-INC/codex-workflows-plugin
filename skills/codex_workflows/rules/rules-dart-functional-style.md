# DIRECTIVE: STRICT FUNCTIONAL PROGRAMMING STYLE (DART)

**CRITICAL MANDATE:** You MUST write all Dart code using a strict functional programming paradigm by default. Apply these rules autonomously to all code generation and refactoring tasks.

## 🚫 PROHIBITED PATTERNS (NEVER USE)

1. **No Imperative Branching:** NEVER use imperative `if/else` code blocks for control flow. You MUST use Dart's native pattern matching (`switch` expressions) or functional mapping.
2. **No Variable Mutation/Declarations:** Avoid intermediate variable declarations. Rely on function chaining, expression bodies, and data transformations.
3. **No Void Functions:** Avoid writing functions that do not return a value. Side-effects must be extremely rare, heavily isolated, and only used when absolutely inevitable.

## ✅ REQUIRED LIBRARIES & PATTERNS (ALWAYS USE)

You must extensively leverage modern Dart features and the **Dartz** package:

1. **Async Operations:** ALWAYS encapsulate asynchronous operations using `Task` from the Dartz package.
2. **Null Safety:** ALWAYS handle nullable return values using `Option` from the Dartz package rather than native null checks.
3. **Error Handling:** Use `Either` for success/failure flows to avoid throwing and catching exceptions imperatively.
4. **Pattern Matching:** Use Dart 3+ native pattern matching exclusively for conditional logic.
5. **Pure Functions:** Default to writing pure, deterministic functions.

## 📖 REFERENCE IMPLEMENTATION

*Observe how async operations are chained via `Task` and `attempt()`, and how lists are transformed without intermediate variables or loops.*

```dart
// Example 1: Functional Async Handling with Task & Either
@override
Future<Either<Failure, Nothing>> deleteAttendance({
  required CallContext callContext,
  required AttendanceSummary attendance,
}) {
  return _dataSource.firestoreRequest<Nothing>(
    (collections) {
      return Task(
            () => _applyDeleteAttendanceOps(
              collections: collections,
              studentPath: _generateStudentDocumentPath(studentId: attendance.studentId),
              summary: attendance,
              dataSource: _dataSource,
              batch: _dataSource.newWriteBatch(),
            ).commit(),
          )
          .attempt() // Converts exceptions into Either (Left/Right)
          .mapLeft((e) => UnknownFailure(innerMessage: 'Error deleting attendance, $e', innerError: e))
          .mapRight((_) => const Nothing())
          .run();
    },
  );
}

// Example 2: Functional Data Transformation (No imperative loops/variables)
List<AttendanceSummary> _mergeAttendances(
  QuerySnapshot<AttendancesByMonthDataModel> monthlySnapshot,
  QuerySnapshot<Attendance> localSnapshot,
) {
  if (monthlySnapshot.metadata.isFromCache) {
    return localSnapshot.docs
        .map((doc) => doc.data())
        .map(AttendanceSummary.fromAttendance)
        .toList();
  }

  return monthlySnapshot.docs
      .map((doc) => doc.data())
      .expand((month) => month.summaries.values)
      .map((summary) => summary.toModel())
      .toList();
}
```
