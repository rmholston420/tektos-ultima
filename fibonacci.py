def fibonacci_iterative(n):
    """Returns the nth Fibonacci number using an iterative approach.
    Time Complexity: O(n)
    Space Complexity: O(1)
    """
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def fibonacci_recursive(n, memo=None):
    """Returns the nth Fibonacci number using a recursive approach with memoization.
    Time Complexity: O(n)
    Space Complexity: O(n) for the recursion stack and memo dictionary.
    """
    if memo is None:
        memo = {}
    
    if n in memo:
        return memo[n]
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    
    memo[n] = fibonacci_recursive(n - 1, memo) + fibonacci_recursive(n - 2, memo)
    return memo[n]

if __name__ == "__main__":
    n = 10
    print(f"Calculating Fibonacci({n})...")
    print(f"Iterative:  {fibonacci_iterative(n)}")
    print(f"Recursive:  {fibonacci_recursive(n)}")
