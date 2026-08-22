# Riverpod Hooks (`flutter_hooks` + `hooks_riverpod`)

> **Source:** [Riverpod Docs — About hooks](https://riverpod.dev/docs/concepts/about_hooks)

## Overview

Hooks are functions used inside widgets, designed as an alternative to `StatefulWidget` for making logic more reusable and composable. They originate from React and are ported to Flutter via `flutter_hooks`.

> **Key distinction:** If Riverpod providers are for **global/shared application state**, hooks are for **local widget state**.

## When to Use Hooks

Hooks are helpful for:

- Forms
- Animations
- Reacting to user events
- Managing `TextEditingController`, `AnimationController`, etc.
- Replacing builder widgets (`FutureBuilder`, `TweenAnimationBuilder`) to reduce nesting

## When NOT to Use Hooks

- If you are a newcomer to Riverpod — avoid hooks initially
- Hooks are NOT needed for Riverpod — they are a separate optional addition
- Hooks are NOT a core Flutter concept — they can feel out of place

## The Rules of Hooks

1. Hooks can **only** be used within the `build` method of a widget that extends `HookWidget` or `HookConsumerWidget`
2. Hooks **cannot** be used conditionally or inside loops

```dart
// ✅ GOOD
class Example extends HookWidget {
  @override
  Widget build(BuildContext context) {
    final controller = useAnimationController();
    // ...
  }
}

// ❌ BAD — Not a HookWidget
class Example extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final controller = useAnimationController(); // Will fail
  }
}

// ❌ BAD — Inside a conditional
class Example extends HookWidget {
  @override
  Widget build(BuildContext context) {
    if (condition) {
      final controller = useAnimationController(); // Not allowed
    }
  }
}
```

## Installation

1. Install `flutter_hooks` separately — `hooks_riverpod` alone is not enough
2. Add both to `pubspec.yaml`:

```yaml
dependencies:
  flutter_hooks: ^latest
  hooks_riverpod: ^latest
```

## Using Hooks with Riverpod

Since `HookWidget` and `ConsumerWidget` cannot both be extended simultaneously, use `hooks_riverpod`:

### Option 1: `HookConsumerWidget` (Preferred)

```dart
class Example extends HookConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final counter = useState(0);
    final value = ref.watch(myProvider);
    return Text('Hello $counter $value');
  }
}
```

### Option 2: Builder Pattern (No `hooks_riverpod` needed)

```dart
class Example extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer(
      builder: (context, ref, child) {
        return HookBuilder(
          builder: (context) {
            final counter = useState(0);
            final value = ref.watch(myProvider);
            return Text('Hello $counter $value');
          },
        );
      },
    );
  }
}
```

### Option 3: `HookConsumer` (Combined Builder)

```dart
class Example extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return HookConsumer(
      builder: (context, ref, child) {
        final counter = useState(0);
        final value = ref.watch(myProvider);
        return Text('Hello $counter $value');
      },
    );
  }
}
```

## Common Hooks

| Hook | Purpose |
| --- | --- |
| `useState` | Simple local state (equivalent to `setState`) |
| `useEffect` | Equivalent to `initState` + `didUpdateWidget` + `dispose` |
| `useAnimationController` | Create and auto-dispose an `AnimationController` |
| `useTextEditingController` | Create and auto-dispose a `TextEditingController` |
| `useMemoized` | Cache expensive computations |
| `useAnimation` | Rebuild widget when animation updates |

## Key Principle

> Hooks are for **local widget state** only. They are NOT a replacement for Riverpod providers.
> Use providers for shared/global state and business logic. Use hooks for ephemeral widget-level concerns.
