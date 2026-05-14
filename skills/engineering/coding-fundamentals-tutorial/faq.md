# FAQ — Common Beginner Questions

---

## Setup

### How do I run Python on my computer?

**Mac / Linux**: Python 3 is usually pre-installed. Open Terminal and type:
```bash
python3 --version
```
If you see `Python 3.x.x`, you're ready. Run a file with:
```bash
python3 exercise.py
```

**Windows**: Download Python from python.org. During installation, check "Add Python to PATH". Then open Command Prompt or PowerShell:
```bash
python --version
python exercise.py
```

**Online (no installation)**: Use [python.org/shell](https://www.python.org/shell) or [replit.com](https://replit.com) to run Python in your browser.

---

### What editor should I use?

- **VS Code** — free, beginner-friendly, great Python support (install the Python extension)
- **Thonny** — designed for beginners, shows variable values while running
- **PyCharm Community** — full-featured Python IDE, free version available
- Any plain text editor works too

---

## Python Concepts

### Why does indentation matter in Python?

Python uses indentation (spaces/tabs at the start of lines) to define code blocks, instead of `{}` curly braces like many other languages.

```python
# Correct — the print is INSIDE the if block
if True:
    print("This runs")

# Wrong — IndentationError
if True:
print("This crashes")
```

**Rule**: Use 4 spaces for each level of indentation. Never mix tabs and spaces.

---

### What's the difference between `=` and `==`?

| Symbol | Meaning | Example |
|--------|---------|---------|
| `=` | Assignment — store a value | `age = 25` |
| `==` | Comparison — check if equal | `if age == 25:` |

A common mistake:
```python
# This assigns 25 to age inside the if — usually not what you want
if age = 25:   # SyntaxError in Python (good — Python protects you)

# This checks if age equals 25 — correct
if age == 25:
```

---

### What is a function vs. a variable?

| | Variable | Function |
|---|---|---|
| **What it is** | A labelled box holding a value | A named block of instructions |
| **How to create** | `name = "Anna"` | `def greet(name):` |
| **How to use** | `print(name)` | `greet("Anna")` |
| **Returns a value?** | It *is* the value | Can return a value with `return` |

---

### What does `int()`, `str()`, `float()` do?

They convert values between types.

```python
age_text = input("How old are you? ")  # input() always returns text (str)
age_number = int(age_text)             # convert to integer for math

print(age_number + 1)  # works: 26
print(age_text + 1)    # TypeError: can't add text and number
```

Use `str()` when you want to combine numbers with text:
```python
age = 25
print("I am " + str(age) + " years old.")
```

---

### Why does my program print nothing / crash immediately?

Common reasons:
1. **Indentation error** — check that lines inside `if`/`for`/`def` are indented by 4 spaces
2. **Syntax error** — missing `:` after `if`, `for`, `def`, or `while`
3. **NameError** — using a variable before assigning it
4. **TypeError** — mixing types (e.g. adding a number to a string without converting)

Read the error message — Python tells you the line number and the type of error. Start there.

---

### What does `#` do?

`#` starts a comment. Python ignores everything after it on that line. Use comments to explain *why* something works the way it does.

```python
birth_year = 2025 - age  # subtract age from current year
```

---

### How do I loop through a list with a number/index?

Use `enumerate()`:
```python
fruits = ["apple", "banana", "cherry"]

for i, fruit in enumerate(fruits, start=1):
    print(i, fruit)
# 1 apple
# 2 banana
# 3 cherry
```

---

### What's `len()`?

`len()` returns the number of items in a list, or the number of characters in a string.

```python
print(len("hello"))       # 5
print(len([1, 2, 3, 4]))  # 4
```
