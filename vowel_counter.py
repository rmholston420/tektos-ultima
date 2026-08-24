VOWELS = set("aeiouAEIOU")


def count_vowels(s):
    return sum(1 for c in s if c in VOWELS)


def get_vowel_indices(s):
    return [i for i, c in enumerate(s) if c in VOWELS]


def main():
    text = "Hello World"
    print(f"Text: {text}")
    print(f"Vowel count: {count_vowels(text)}")
    print(f"Vowel indices: {get_vowel_indices(text)}")


if __name__ == "__main__":
    main()
