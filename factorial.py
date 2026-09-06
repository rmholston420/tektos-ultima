def factorial(n):
    """Calculate the factorial of a non-negative integer.
    
    Args:
        n: A non-negative integer.
        
    Returns:
        The factorial of n (n!).
        
    Raises:
        TypeError: If n is not an integer.
        ValueError: If n is negative.
    """
    # Check if input is an integer (but not a bool, since bool is a subclass of int)
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"Input must be an integer, got {type(n).__name__}")
    
    # Check for negative numbers
    if n < 0:
        raise ValueError(f"Input must be a non-negative integer, got {n}")
    
    # Base case: 0! = 1 and 1! = 1
    if n == 0 or n == 1:
        return 1
    
    # Iterative calculation
    result = 1
    for i in range(2, n + 1):
        result *= i
    
    return result


if __name__ == "__main__":
    # Test valid inputs
    for num in range(11):
        print(f"{num}! = {factorial(num)}")
    
    print()
    
    # Test error handling
    test_cases = [-1, 3.5, "5", True]
    for tc in test_cases:
        try:
            factorial(tc)
        except (TypeError, ValueError) as e:
            print(f"factorial({tc!r}) raised {type(e).__name__}: {e}")
