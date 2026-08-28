def fibonacci(n):
    """Calculate the nth Fibonacci number recursively."""
    if n < 0:
        raise ValueError("Input must be a non-negative integer.")
    if n == 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)


if __name__ == "__main__":
    for i in range(11):
        print(f"Fibonacci({i}) = {fibonacci(i)}")
