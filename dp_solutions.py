class CoinChange:
    def min_coins(self, coins, amount):
        dp = [amount + 1] * (amount + 1)
        dp[0] = 0
        for a in range(1, amount + 1):
            for c in coins:
                if a >= c:
                    dp[a] = min(dp[a], dp[a - c] + 1)
        return dp[amount] if dp[amount] <= amount else -1


class LongestCommonSubsequence:
    def lcs(self, s1, s2):
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[m][n]


class Knapsack:
    def max_value(self, weights, values, capacity):
        n = len(weights)
        dp = [[0] * (capacity + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            for w in range(capacity + 1):
                dp[i][w] = dp[i - 1][w]
                if weights[i - 1] <= w:
                    dp[i][w] = max(dp[i][w], dp[i - 1][w - weights[i - 1]] + values[i - 1])
        return dp[n][capacity]


def main():
    # CoinChange
    cc = CoinChange()
    assert cc.min_coins([1, 2, 5], 11) == 3   # 5+5+1
    assert cc.min_coins([2], 3) == -1
    assert cc.min_coins([1], 0) == 0
    print("CoinChange: all tests passed")

    # LCS
    lcs = LongestCommonSubsequence()
    assert lcs.lcs("ABCDGH", "AEDFHR") == 3   # ADH
    assert lcs.lcs("", "ABC") == 0
    assert lcs.lcs("ABC", "ABC") == 3
    print("LCS: all tests passed")

    # Knapsack
    kn = Knapsack()
    assert kn.max_value([1, 2, 3], [10, 15, 40], 6) == 65   # all three: 1+2+3=6, 10+15+40=65
    assert kn.max_value([2, 3, 4, 5], [1, 2, 3, 4], 8) == 6  # (3,2)+(5,4)=8, value=6
    assert kn.max_value([], [], 10) == 0
    print("Knapsack: all tests passed")


if __name__ == "__main__":
    main()
