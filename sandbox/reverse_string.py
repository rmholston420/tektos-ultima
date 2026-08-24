def reverse_string(s):
    return s[::-1]

def is_palindrome(s):
    return s == s[::-1]

def main():
    tests = ["hello", "racecar", "Python", "madam", "a"]
    for t in tests:
        print(f"{t} -> {reverse_string(t)} | Palindrome: {is_palindrome(t)}")

if __name__ == "__main__":
    main()
