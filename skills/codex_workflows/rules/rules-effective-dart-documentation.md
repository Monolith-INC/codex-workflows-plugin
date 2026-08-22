---
trigger: always_on
title: "Effective Dart: Documentation"
breadcrumb: Documentation
description: Clear, helpful comments and documentation.
nextpage:
  url: /effective-dart/usage
  title: Usage
prevpage:
  url: /effective-dart/style
  title: Style
---

# Effective Dart documentation

<?code-excerpt path-base="misc/lib/effective_dart"?>

It's easy to think your code is obvious today without realizing how much you
rely on context already in your head. People new to your code, and
even your forgetful future self won't have that context. A concise, accurate
comment only takes a few seconds to write but can save one of those people
hours of time.

We all know code should be self-documenting and not all comments are helpful.
But the reality is that most of us don't write as many comments as we should.
It's like exercise: you technically *can* do too much, but it's a lot more
likely that you're doing too little. Try to step it up.

## Comments

The following tips apply to comments that you don't want included in the
generated documentation.

### DO format comments like sentences

<?code-excerpt "docs_good.dart (comments-like-sentences)"?>

```dart tag=good
// Not if anything comes before it.
if (_chunks.isNotEmpty) return false;
```

Capitalize the first word unless it's a case-sensitive identifier. End it with a
period (or "!" or "?", I suppose). This is true for all comments: doc comments,
inline stuff, even TODOs. Even if it's a sentence fragment.

### DON'T use block comments for documentation

<?code-excerpt "docs_good.dart (block-comments)"?>

```dart tag=good
void greet(String name) {
  // Assume we have a valid name.
  print('Hi, $name!');
}
```

<?code-excerpt "docs_bad.dart (block-comments)"?>

```dart tag=bad
void greet(String name) {
  /* Assume we have a valid name. */
  print('Hi, $name!');
}
```

You can use a block comment (`/* ... */`) to temporarily comment out a section
of code, but all other comments should use `//`.

## Doc comments

Doc comments are especially handy because [`dart doc`][] parses them
and generates [beautiful doc pages][docs] from them.
A doc comment is any comment that appears before a declaration
and uses the special `///` syntax that `dart doc` looks for.

[`dart doc`]: /tools/dart-doc
[docs]: {{site.dart-api}}

### DO use `///` doc comments to document members and types

{% render 'linter-rule-mention.md', rules:'slash_for_doc_comments' %}

Using a doc comment instead of a regular comment enables
[`dart doc`][] to find it
and generate documentation for it.

<?code-excerpt "docs_good.dart (use-doc-comments)"?>

```dart tag=good
/// The number of characters in this chunk when unsplit.
int get length => ...
```

<?code-excerpt "docs_good.dart (use-doc-comments)" replace="/^\///g"?>

```dart tag=bad
// The number of characters in this chunk when unsplit.
int get length => ...
```

For historical reasons, `dart doc` supports two syntaxes of doc comments: `///`
("C# style") and `/** ... */` ("JavaDoc style"). We prefer `///` because it's
more compact. `/**` and `*/` add two content-free lines to a multiline doc
comment. The `///` syntax is also easier to read in some situations, such as
when a doc comment contains a bulleted list that uses `*` to mark list items.

If you stumble onto code that still uses the JavaDoc style, consider cleaning it
up.

### PREFER writing doc comments for public APIs

{% render 'linter-rule-mention.md', rules:'public_member_api_docs' %}

You don't have to document every single library, top-level variable, type, and
member, but you should document most of them.

### CONSIDER writing a library-level doc comment

Unlike languages like Java where the class is the only unit of program
organization, in Dart, a library is itself an entity that users work with
directly, import, and think about. That makes the `library` directive a great
place for documentation that introduces the reader to the main concepts and
functionality provided within. Consider including:

* A single-sentence summary of what the library is for.
* Explanations of terminology used throughout the library.
* A couple of complete code samples that walk through using the API.
* Links to the most important or most commonly used classes and functions.
* Links to external references on the domain the library is concerned with.

To document a library, place a doc comment before
the `library` directive and any annotations that might be attached
at the start of the file.

<?code-excerpt "docs_good.dart (library-doc)"?>

```dart tag=good
/// A really great test library.
@TestOn('browser')
library;
```

### CONSIDER writing doc comments for private APIs

Doc comments aren't just for external consumers of your library's public API.
They can also be helpful for understanding private members that are called from
other parts of the library.

### DO start doc comments with a single-sentence summary

Start your doc comment with a brief, user-centric description ending with a
period. A sentence fragment is often sufficient. Provide just enough context for
the reader to orient themselves and decide if they should keep reading or look
elsewhere for the solution to their problem.

<?code-excerpt "docs_good.dart (first-sentence)"?>

```dart tag=good
/// Deletes the file at [path] from the file system.
void delete(String path) {
  ...
}
```

<?code-excerpt "docs_bad.dart (first-sentence)"?>

```dart tag=bad
/// Depending on the state of the file system and the user's permissions,
/// certain operations may or may not be possible. If there is no file at
/// [path] or it can't be accessed, this function throws either [IOError]
/// or [PermissionError], respectively. Otherwise, this deletes the file.
void delete(String path) {
  ...
}
```

### DO separate the first sentence of a doc comment into its own paragraph

Add a blank line after the first sentence to split it out into its own
paragraph. If more than a single sentence of explanation is useful, put the
rest in later paragraphs.

This helps you write a tight first sentence that summarizes the documentation.
Also, tools like `dart doc` use the first paragraph as a short summary in places
like lists of classes and members.

<?code-excerpt "docs_good.dart (first-sentence-a-paragraph)"?>

```dart tag=good
/// Deletes the file at [path].
///
/// Throws an [IOError] if the file could not be found. Throws a
/// [PermissionError] if the file is present but could not be deleted.
void delete(String path) {
  ...
}
```

<?code-excerpt "docs_bad.dart (first-sentence-a-paragraph)"?>

```dart tag=bad
/// Deletes the file at [path]. Throws an [IOError] if the file could not
/// be found. Throws a [PermissionError] if the file is present but could
/// not be deleted.
void delete(String path) {
  ...
}
```

### AVOID redundancy with the surrounding context

The reader of a class's doc comment can clearly see the name of the class, what
interfaces it implements, etc. When reading docs for a member, the signature is
right there, and the enclosing class is obvious. None of that needs to be
spelled out in the doc comment. Instead, focus on explaining what the reader
*doesn't* already know.

<?code-excerpt "docs_good.dart (redundant)"?>

```dart tag=good
class RadioButtonWidget extends Widget {
  /// Sets the tooltip to [lines].
  ///
  /// The lines should be word wrapped using the current font.
  void tooltip(List<String> lines) {
    ...
  }
}
```

<?code-excerpt "docs_bad.dart (redundant)"?>

```dart tag=bad
class RadioButtonWidget extends Widget {
  /// Sets the tooltip for this radio button widget to the list of strings in
  /// [lines].
  void tooltip(List<String> lines) {
    ...
  }
}
```

If you really don't have anything interesting to say
that can't be inferred from the declaration itself,
then omit the doc comment.
It's better to say nothing
than waste a reader's time telling them something they already know.

<a id="prefer-starting-function-or-method-comments-with-third-person-verbs" aria-hidden="true"></a>

### PREFER starting comments of a function or method with third-person verbs if its main purpose is a side effect

The doc comment should focus on what the code *does*.

<?code-excerpt "docs_good.dart (third-person)"?>

```dart tag=good
/// Connects to the server and fetches the query results.
Stream<QueryResult> fetchResults(Query query) => ...

/// Starts the stopwatch if not already running.
void start() => ...
```

### PREFER starting a non-boolean variable or property comment with a noun phrase

The doc comment should stress what the property *is*. This is true even for
getters which may do calculation or other work. What the caller cares about is
the *result* of that work, not the work itself.

<?code-excerpt "docs_good.dart (noun-phrases-for-non-boolean-var-etc)"?>

```dart tag=good
/// The current day of the week, where `0` is Sunday.
int weekday;

/// The number of checked buttons on the page.
int get checkedCount => ...
```

### PREFER starting a boolean variable or property comment with "Whether" followed by a noun or gerund phrase

The doc comment should clarify the states this variable represents.
This is true even for getters which may do calculation or other work.
What the caller cares about is the *result* of that work, not the work itself.

<?code-excerpt "docs_good.dart (noun-phrases-for-boolean-var-etc)"?>

```dart tag=good
/// Whether the modal is currently displayed to the user.
bool isVisible;

/// Whether the modal should confirm the user's intent on navigation.
bool get shouldConfirm => ...

/// Whether resizing the current browser window will also resize the modal.
bool get canResize => ...
```

:::note
This guideline intentionally doesn't include using "Whether or not". In many
cases, usage of "or not" with "whether" is superfluous and can be omitted,
especially when used in this context.
:::

### PREFER a noun phrase or non-imperative verb phrase for a function or method if returning a value is its primary purpose

If a method is *syntactically* a method, but *conceptually* it is a property,
and is therefore [named with a noun phrase or non-imperative verb phrase][parameterized_property_name],
it should also be documented as such.
Use a noun-phrase for such non-boolean functions, and
a phrase starting with "Whether" for such boolean functions,
just as for a syntactic property or variable.

<?code-excerpt "docs_good.dart (noun-for-func-returning-value)"?>

```dart tag=good
/// The [index]th element of this iterable in iteration order.
E elementAt(int index);

/// Whether this iterable contains an element equal to [element].
bool contains(Object? element);
```

:::note
This guideline should be applied based on whether the declaration is
conceptually seen as a property.

Sometimes a method has no side effects, and might
conceptually be seen as a property, but is still
simpler to name with a verb phrase like `list.take()`.
Then a noun phrase should still be used to document it.
*For example `Iterable.take` can be described as
"The first \[count\] elements of ...".*
:::

[parameterized_property_name]: design#prefer-a-noun-phrase-or-non-imperative-verb-phrase-for-a-function-or-method-if-returning-a-value-is-its-primary-purpose

### DON'T write documentation for both the getter and setter of a property

If a property has both a getter and a setter, then create a doc comment for
only one of them. `dart doc` treats the getter and setter like a single field,
and if both the getter and the setter have doc comments, then
`dart doc` discards the setter's doc comment.

<?code-excerpt "docs_good.dart (getter-and-setter)"?>

```dart tag=good
/// The pH level of the water in the pool.
///
/// Ranges from 0-14, representing acidic to basic, with 7 being neutral.
int get phLevel => ...
set phLevel(int level) => ...
```

<?code-excerpt "docs_bad.dart (getter-and-setter)"?>

```dart tag=bad
/// The depth of the water in the pool, in meters.
int get waterDepth => ...

/// Updates the water depth to a total of [meters] in height.
set waterDepth(int meters) => ...
`
