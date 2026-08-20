from typing import List, TypeVar

# Define a generic type variable to allow sorting of different types
T = TypeVar('T')

def quicksort(arr: List[T]) -> List[T]:
    """
    Sorts a list using the Quicksort algorithm.
    
    Args:
        arr: The list of elements to sort.
        
    Returns:
        A new list containing the sorted elements.
        
    Note:
        This implementation creates new lists during partitioning.
        For an in-place version that modifies the list directly, 
        a different approach with indices is required.
    """
    # Base case: lists with 0 or 1 element are already sorted
    if len(arr) <= 1:
        return arr
    
    # Choose the middle element as the pivot
    pivot = arr[len(arr) // 2]
    
    # Partition the list into three parts using list comprehensions
    left = [x for x in arr if x < pivot]      # Elements less than pivot
    middle = [x for x in arr if x == pivot]   # Elements equal to pivot
    right = [x for x in arr if x > pivot]     # Elements greater than pivot
    
    # Recursively sort the left and right parts and combine with middle
    return quicksort(left) + middle + quicksort(right)

if __name__ == "__main__":
    # Example usage
    data = [38, 27, 43, 3, 9, 82, 10]
    print(f"Original list: {data}")
    
    sorted_data = quicksort(data)
    print(f"Sorted list:   {sorted_data}")
