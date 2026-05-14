# Curriculum

Full chapter and concept list for the coding fundamentals tutorial.

---

## Chapter 1 — Foundations

**Goal**: Understand how a program stores and displays information.

### Concept 1.1 — Variables & Types

**Analogy**: A variable is a labelled box. You put something inside (`=`), give it a name, and retrieve it later by name.

**Types to cover**:
- `str` — text, always in quotes: `"hello"`
- `int` — whole number: `42`
- `float` — decimal number: `3.14`
- `bool` — True or False

**Example**:
```python
name = "Anna"
age = 28
height = 1.72
is_student = True

print(name)
print(age)
```

**Exercise**: Create three variables — your name, your age, and your favourite number — then print all three.

---

### Concept 1.2 — print() and input()

**Analogy**: `print()` is the program speaking to you. `input()` is the program listening.

**Example**:
```python
name = input("What is your name? ")
print("Hello,", name)
```

**Exercise**: Write a program that asks for the user's name and their favourite colour, then prints: `"Hi [name], [colour] is a great colour!"`

---

### Chapter 1 Mini-Project — Personalised Greeter

Build a program that:
1. Asks for the user's name and age
2. Calculates what year they were born (hint: use `2025 - age`)
3. Prints: `"Hello [name]! You were born in [year]."`

---

## Chapter 2 — Logic

**Goal**: Make decisions in code.

### Concept 2.1 — if / elif / else

**Analogy**: Like a traffic light — different actions depending on the situation.

**Example**:
```python
temperature = 22

if temperature > 30:
    print("It's hot!")
elif temperature > 15:
    print("It's warm.")
else:
    print("It's cold.")
```

**Exercise**: Write a program that asks for a number and prints whether it is positive, negative, or zero.

---

### Concept 2.2 — Comparison & Boolean Operators

**Operators**: `==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`

**Analogy**: `and` = both must be true; `or` = at least one must be true; `not` = flip it.

**Example**:
```python
age = 20
has_ticket = True

if age >= 18 and has_ticket:
    print("You can enter.")
else:
    print("Sorry, you cannot enter.")
```

**Exercise**: Write a simple login checker — ask for a username and password, and print "Welcome!" only if both match hardcoded values.

---

### Chapter 2 Mini-Project — Age & Category Checker

Build a program that:
1. Asks for the user's age
2. Prints their category: Child (< 13), Teen (13–17), Adult (18–64), Senior (65+)

---

## Chapter 3 — Repetition

**Goal**: Repeat actions without copy-pasting code.

### Concept 3.1 — for loops & range()

**Analogy**: "Do this 5 times" or "do this for each item in a list."

**Example**:
```python
for i in range(5):
    print("Step", i)
```

**Exercise**: Print a countdown from 10 to 1 using a for loop.

---

### Concept 3.2 — while loops

**Analogy**: "Keep going until something changes."

**Example**:
```python
password = ""
while password != "secret":
    password = input("Enter the password: ")
print("Access granted!")
```

**Exercise**: Write a guessing game — pick a secret number, keep asking the user to guess until they get it right.

---

### Chapter 3 Mini-Project — Multiplication Table

Print the full multiplication table for a number the user chooses (1 × n through 10 × n).

---

## Chapter 4 — Collections

**Goal**: Store and work with multiple values.

### Concept 4.1 — Lists

**Analogy**: A numbered queue — order matters, items can be added or removed.

**Example**:
```python
fruits = ["apple", "banana", "cherry"]
fruits.append("mango")
print(fruits[0])   # apple
print(len(fruits)) # 4
```

**Exercise**: Create a list of 3 favourite foods. Add one more. Print each food on a separate line using a for loop.

---

### Concept 4.2 — Dictionaries

**Analogy**: A real dictionary — look up a word (key) to get its meaning (value).

**Example**:
```python
person = {
    "name": "Lena",
    "age": 25,
    "city": "Berlin"
}
print(person["name"])
person["age"] = 26
```

**Exercise**: Create a dictionary for a movie (title, year, director). Print each value with a label, e.g. `"Title: Inception"`.

---

### Chapter 4 Mini-Project — Shopping List Manager

Build a program that:
1. Starts with an empty list
2. Lets the user type items to add (type "done" to stop)
3. Prints the final shopping list numbered, e.g. `"1. Milk"`

---

## Chapter 5 — Functions

**Goal**: Package reusable logic with a name.

### Concept 5.1 — Defining & Calling Functions

**Analogy**: A function is a recipe — you write it once, use it many times.

**Example**:
```python
def greet(name):
    print("Hello,", name)

greet("Anna")
greet("Tom")
```

**Exercise**: Write a function `double(number)` that returns the number multiplied by 2. Call it with three different numbers.

---

### Concept 5.2 — Return Values & Scope

**return** sends a value back to the caller. Variables inside a function are local — they don't exist outside.

**Example**:
```python
def add(a, b):
    return a + b

result = add(3, 5)
print(result)  # 8
```

**Exercise**: Write a function `celsius_to_fahrenheit(c)` that converts a Celsius temperature to Fahrenheit (`f = c * 9/5 + 32`). Print the result for 0°, 20°, and 100°.

---

### Chapter 5 Mini-Project — Calculator

Build a calculator with four functions: `add`, `subtract`, `multiply`, `divide`. Ask the user for two numbers and an operation, then call the right function and print the result.

---

## Chapter 6 — First Real App

**Goal**: Combine all concepts into a working CLI application.

### Project — Mini To-Do List

Build a command-line to-do list manager with these features:

1. **Add** a task
2. **List** all tasks (with a number and a ✓ or ✗ for done/not done)
3. **Complete** a task by number
4. **Quit**

**Starting structure**:
```python
tasks = []  # each task: {"title": "...", "done": False}

def add_task(title):
    pass  # your code here

def list_tasks():
    pass  # your code here

def complete_task(number):
    pass  # your code here

while True:
    action = input("Action (add / list / complete / quit): ")
    # your logic here
```

The full starter is in [exercises.md](exercises.md).

---

## What's Next After Chapter 6?

Once the mini to-do app works, the learner is ready for:

- **File I/O** — save tasks to a `.txt` or `.json` file so they persist between runs
- **Modules & imports** — split code across multiple files
- **Web development** — Flask or FastAPI for building web APIs
- **Data & automation** — `requests` library to call APIs, `pandas` for spreadsheets
