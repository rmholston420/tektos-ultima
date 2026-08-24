def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break

def is_sorted(arr):
    return all(arr[i] <= arr[i + 1] for i in range(len(arr) - 1))

def main():
    tests = [[3, 1, 4, 1, 5], [], [1], [2, 1], [5, 4, 3, 2, 1]]
    for arr in tests:
        bubble_sort(arr)
        assert is_sorted(arr), f"Failed: {arr}"
        print(f"{arr}")
    print("All tests passed.")

if __name__ == "__main__":
    main()
