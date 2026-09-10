def fibonacci(n, cache=None):
    if cache is None:
        cache = {}
    if n in cache:
        return cache[n]
    if n < 2:
        return n
    cache[n] = fibonacci(n - 1, cache) + fibonacci(n - 2, cache)
    return cache[n]

def main():
    for i in range(10):
        print(fibonacci(i))

if __name__ == "__main__":
    main()
