# Exercise Starters

Runnable Python starter files for each chapter's exercises and mini-projects. Copy a snippet into a `.py` file (e.g. `exercise.py`), run it with `python3 exercise.py`, and fill in the blanks.

---

## Chapter 1 — Foundations

### Exercise 1.1 — Variables starter
```python
# Fill in your own values
name = "..."
age = ...
favourite_number = ...

# Print all three
print(name)
print(age)
print(favourite_number)
```

### Exercise 1.2 — Input / Output starter
```python
name = input("What is your name? ")
colour = input("What is your favourite colour? ")

# Print: "Hi [name], [colour] is a great colour!"
print(...)
```

### Mini-Project 1 — Personalised Greeter starter
```python
name = input("What is your name? ")
age = int(input("How old are you? "))  # int() converts text to a number

birth_year = ...  # calculate this

print("Hello " + name + "! You were born in " + str(birth_year) + ".")
```

---

## Chapter 2 — Logic

### Exercise 2.1 — Positive / Negative / Zero starter
```python
number = int(input("Enter a number: "))

if ...:
    print("Positive")
elif ...:
    print("Negative")
else:
    print("Zero")
```

### Exercise 2.2 — Login checker starter
```python
correct_username = "admin"
correct_password = "secret123"

username = input("Username: ")
password = input("Password: ")

if ... and ...:
    print("Welcome!")
else:
    print("Incorrect username or password.")
```

### Mini-Project 2 — Age Category starter
```python
age = int(input("Enter your age: "))

if age < 13:
    print("Child")
elif ...:
    print("Teen")
elif ...:
    print("Adult")
else:
    print("Senior")
```

---

## Chapter 3 — Repetition

### Exercise 3.1 — Countdown starter
```python
# Print 10, 9, 8, ... 1 using range()
for i in range(..., ..., ...):
    print(i)
```

### Exercise 3.2 — Guessing game starter
```python
secret = 7  # change this to any number

guess = 0
while guess != secret:
    guess = int(input("Guess the number: "))
    if guess < secret:
        print("Too low!")
    elif guess > secret:
        print("Too high!")

print("Correct!")
```

### Mini-Project 3 — Multiplication table starter
```python
n = int(input("Enter a number: "))

for i in range(1, 11):
    result = ...
    print(n, "x", i, "=", result)
```

---

## Chapter 4 — Collections

### Exercise 4.1 — Favourite foods starter
```python
foods = ["Pizza", "Sushi", "Tacos"]
foods.append("...")

for food in foods:
    print(food)
```

### Exercise 4.2 — Movie dictionary starter
```python
movie = {
    "title": "...",
    "year": ...,
    "director": "..."
}

print("Title:", movie["title"])
print("Year:", ...)
print("Director:", ...)
```

### Mini-Project 4 — Shopping list starter
```python
shopping_list = []

while True:
    item = input("Add item (or 'done' to finish): ")
    if item == "done":
        break
    shopping_list.append(item)

print("\nYour shopping list:")
for i, item in enumerate(shopping_list, start=1):
    print(str(i) + ". " + item)
```

---

## Chapter 5 — Functions

### Exercise 5.1 — double() starter
```python
def double(number):
    return ...

print(double(3))   # should print 6
print(double(10))  # should print 20
print(double(7))   # should print 14
```

### Exercise 5.2 — Temperature converter starter
```python
def celsius_to_fahrenheit(c):
    return ...

print(celsius_to_fahrenheit(0))    # 32.0
print(celsius_to_fahrenheit(20))   # 68.0
print(celsius_to_fahrenheit(100))  # 212.0
```

### Mini-Project 5 — Calculator starter
```python
def add(a, b):
    return a + b

def subtract(a, b):
    return ...

def multiply(a, b):
    return ...

def divide(a, b):
    return ...

a = float(input("First number: "))
b = float(input("Second number: "))
op = input("Operation (add / subtract / multiply / divide): ")

if op == "add":
    print(add(a, b))
elif op == "subtract":
    print(...)
elif op == "multiply":
    print(...)
elif op == "divide":
    print(...)
else:
    print("Unknown operation")
```

---

## Chapter 6 — Mini To-Do List (full starter)

```python
tasks = []  # each task is a dict: {"title": "...", "done": False}


def add_task(title):
    tasks.append({"title": title, "done": False})


def list_tasks():
    if len(tasks) == 0:
        print("No tasks yet.")
        return
    for i, task in enumerate(tasks, start=1):
        status = "✓" if task["done"] else "✗"
        print(str(i) + ". [" + status + "] " + task["title"])


def complete_task(number):
    index = number - 1
    if index < 0 or index >= len(tasks):
        print("Invalid task number.")
        return
    tasks[index]["done"] = True
    print("Marked as done:", tasks[index]["title"])


print("=== Mini To-Do List ===")
while True:
    action = input("\nAction (add / list / complete / quit): ").strip().lower()

    if action == "add":
        title = input("Task title: ")
        add_task(title)
        print("Added:", title)
    elif action == "list":
        list_tasks()
    elif action == "complete":
        list_tasks()
        num = int(input("Which task number? "))
        complete_task(num)
    elif action == "quit":
        print("Goodbye!")
        break
    else:
        print("Unknown action. Try: add, list, complete, quit")
```
