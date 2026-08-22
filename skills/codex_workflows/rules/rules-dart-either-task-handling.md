# Functional Error Handling with Dartz (Either & Task)

This rule defines the standard for handling errors and asynchronous operations using the `dartz` package, specifically `Either` and `Task`.

## 1. Core Principle: `Either<Failure, T>`

Avoid throwing exceptions for expected errors. Instead, return an `Either<Failure, T>` type.

- **Left**: Represents a `Failure` (domain error).
- **Right**: Represents a Success value of type `T`.

### Usage

When defining repository or service methods, the return type should be `Future<Either<Failure, T>>`.

```dart
Future<Either<Failure, User>> getUser(String id);
```

## 2. Handling Results: `fold`

Always use the `.fold()` method to handle the result. This ensures both success and failure cases are explicitly handled (compile-time safety).

```dart
final result = await service.getUser('123');

result.fold(
  (failure) {
    // Handle failure (e.g., show error message)
    showError(failure.message);
  },
  (user) {
    // Handle success
    displayUser(user);
  },
);
```

**DO NOT** Use `if (result.isLeft())` checks. Use `fold`.

## 3. Asynchronous Operations: `Task`

Use `Task` to compose asynchronous operations and handle exceptions in a functional way.

### Pattern

1. **Wrap**: Wrap the `Future` call in a `Task`.
2. **Attempt**: Use `.attempt()` to automatically catch all exceptions and convert the result to `Either<Object, T>`.
3. **Map Failure**: Convert the `Object` (exception) on the Left side to a domain `Failure`. RETHROW unexpected exceptions (programming errors).
4. **Run**: Call `.run()` to execute the `Task` and get a standard `Future<Either<Failure, T>>`.

### Implementation Example

```dart
// Define this extension once in your project (e.g., core/utils/task_extensions.dart)
extension TaskX<T extends Either<Object, U>, U> on Task<T> {
  Task<Either<Failure, U>> mapLeftToFailure() {
    return this.map(
      (either) => either.leftMap((obj) {
        try {
          return obj as Failure;
        } catch (e) {
          throw obj; // Rethrow unexpected exceptions (cast error, etc.)
        }
      }),
    );
  }
}

// Usage in a Repository/Service
Future<Either<Failure, Post>> getOnePost() async {
  return await Task(() => _postService.getOnePost())
      .attempt()
      .mapLeftToFailure()
      .run();
}
```

## 4. UI/State Management

When the result reaches the UI or State Management layer (e.g., Bloc, Provider), use `fold` to determine the state.

```dart
void loadPost() async {
  state = NotifierState.loading;
  
  final result = await _repository.getOnePost();
  
  result.fold(
    (failure) => state = NotifierState.error(failure),
    (post) => state = NotifierState.loaded(post),
  );
}
```
