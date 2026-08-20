#!/usr/bin/env python3
"""
Fibonacci Number Generator
Generates Fibonacci numbers using both iterative and generator approaches.
"""

def fibonacci_generator(limit=None, count=None):
    """
    Generator that yields Fibonacci numbers.
    
    Args:
        limit (int, optional): Stop when Fibonacci number exceeds this limit.
        count (int, optional): Generate exactly this many numbers.
        
    Yields:
        int: Next Fibonacci number
    """
    a, b = 0, 1
    n = 0
    while True:
        if limit is not None and a > limit:
            break
        if count is not None and n >= count:
            break
        yield a
        a, b = b, a + b
        n += 1


def fibonacci_list(limit=None, count=None):
    """
    Returns a list of Fibonacci numbers.
    
    Args:
        limit (int, optional): Stop when Fibonacci number exceeds this limit.
        count (int, optional): Generate exactly this many numbers.
        
    Returns:
        list: List of Fibonacci numbers
    """
    return list(fibonacci_generator(limit, count))


def fibonacci_recursive(n, memo={}):
    """
    Calculates the nth Fibonacci number using recursion with memoization.
    
    Args:
        n (int): The position in the Fibonacci sequence (0-indexed).
        memo (dict): Dictionary for memoization.
        
    Returns:
        int: The nth Fibonacci number
    """
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fibonacci_recursive(n - 1, memo) + fibonacci_recursive(n - 2, memo)
    return memo[n]


def main():
    print("=== Fibonacci Generator Demo ===\n")
    
    # 1. Generate first 15 Fibonacci numbers
    print("1. First 15 Fibonacci numbers:")
    fibs = fibonacci_list(count=15)
    print(f"   {fibs}\n")
    
    # 2. Generate Fibonacci numbers up to a limit (e.g., 1000)
    print("2. Fibonacci numbers up to 1000:")
    fibs = fibonacci_list(limit=1000)
    print(f"   {fibs}\n")
    
    # 3. Using the generator directly (memory efficient for large sequences)
    print("3. First 10 Fibonacci numbers (using generator):")
    gen = fibonacci_generator(count=10)
    result = [next(gen) for _ in range(10)]
    print(f"   {result}\n")
    
    # 4. Recursive calculation of specific Fibonacci numbers
    print("4. Recursive calculation (0-indexed):")
    for i in [0, 1, 5, 10, 20]:
        print(f"   F({i}) = {fibonacci_recursive(i)}")
    print()


if __name__ == "__main__":
    main()
