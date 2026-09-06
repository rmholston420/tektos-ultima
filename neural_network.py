"""Pure Python Neural Network from scratch."""

import math
import random


# ── Matrix ──────────────────────────────────────────────────────────────────
class Matrix:
    """Matrix stored as list[list[float]]."""

    def __init__(self, rows, cols=None, data=None):
        if data is not None:
            self.rows = len(data)
            self.cols = len(data[0]) if self.rows else 0
            self.data = [list(row) for row in data]
        else:
            self.rows = rows
            self.cols = cols
            self.data = [[0.0] * cols for _ in range(rows)]

    @classmethod
    def zeros(cls, rows, cols):
        return cls(rows, cols)

    @classmethod
    def ones(cls, rows, cols):
        m = cls(rows, cols)
        for i in range(m.rows):
            for j in range(m.cols):
                m.data[i][j] = 1.0
        return m

    @classmethod
    def random(cls, rows, cols, scale=0.5):
        data = [[random.gauss(0, scale) for _ in range(cols)]
                for _ in range(rows)]
        return cls(rows, cols, data)

    def __add__(self, other):
        m = Matrix(self.rows, self.cols)
        for i in range(self.rows):
            for j in range(self.cols):
                m.data[i][j] = self.data[i][j] + other.data[i][j]
        return m

    def __sub__(self, other):
        m = Matrix(self.rows, self.cols)
        for i in range(self.rows):
            for j in range(self.cols):
                m.data[i][j] = self.data[i][j] - other.data[i][j]
        return m

    def __mul__(self, scalar):
        m = Matrix(self.rows, self.cols)
        for i in range(self.rows):
            for j in range(self.cols):
                m.data[i][j] = self.data[i][j] * scalar
        return m

    def __matmul__(self, other):
        m = Matrix(self.rows, other.cols)
        for i in range(self.rows):
            for j in range(other.cols):
                s = 0.0
                for k in range(self.cols):
                    s += self.data[i][k] * other.data[k][j]
                m.data[i][j] = s
        return m

    def transpose(self):
        m = Matrix(self.cols, self.rows)
        for i in range(self.rows):
            for j in range(self.cols):
                m.data[j][i] = self.data[i][j]
        return m

    def map(self, fn):
        """Return new matrix with fn applied element-wise."""
        m = Matrix(self.rows, self.cols)
        for i in range(self.rows):
            for j in range(self.cols):
                m.data[i][j] = fn(self.data[i][j])
        return m

    def add_inplace(self, other):
        for i in range(self.rows):
            for j in range(self.cols):
                self.data[i][j] += other.data[i][j]
        return self

    def mul_inplace(self, scalar):
        for i in range(self.rows):
            for j in range(self.cols):
                self.data[i][j] *= scalar
        return self

    def copy(self):
        return Matrix(self.rows, self.cols, self.data)


# ── Activations ─────────────────────────────────────────────────────────────
def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))

def sigmoid_deriv(x):
    s = sigmoid(x)
    return s * (1.0 - s)

def relu(x):
    return max(0.0, x)

def relu_deriv(x):
    return 1.0 if x > 0 else 0.0

def tanh_fn(x):
    return math.tanh(x)

def tanh_deriv(x):
    t = math.tanh(x)
    return 1.0 - t * t

def softmax(x):
    m = max(x)
    exps = [math.exp(xi - m) for xi in x]
    s = sum(exps)
    return [e / s for e in exps]


ACTIVATIONS = {
    "sigmoid": (sigmoid, sigmoid_deriv),
    "relu":    (relu, relu_deriv),
    "tanh":    (tanh_fn, tanh_deriv),
}

SOFTMAX = softmax


# ── Dense Layer ─────────────────────────────────────────────────────────────
class Dense:
    def __init__(self, in_dim, out_dim, activation="relu"):
        scale = math.sqrt(2.0 / in_dim)
        self.W = Matrix.random(out_dim, in_dim, scale)
        self.b = Matrix.zeros(out_dim, 1)
        self.activation_name = activation
        self._input = None
        self._pre_act = None
        self._dW = None
        self._db = None
        self._out_dim = out_dim

    def forward(self, X):
        """X: Matrix (batch, in_dim).  Returns Matrix (batch, out_dim)."""
        self._input = X
        z = X @ self.W.transpose() + self.b.transpose()
        self._pre_act = z
        if self.activation_name == "softmax":
            out = Matrix(z.rows, z.cols)
            for i in range(z.rows):
                row = [z.data[i][j] for j in range(z.cols)]
                sm = softmax(row)
                for j, v in enumerate(sm):
                    out.data[i][j] = v
            return out
        act_fn, _ = ACTIVATIONS[self.activation_name]
        return z.map(act_fn)

    def backward(self, dout):
        """dout: Matrix (batch, out_dim) gradient of loss w.r.t. output."""
        batch = dout.rows
        if self.activation_name == "softmax":
            pre = self._pre_act
            da = Matrix(batch, self._out_dim)
            for i in range(batch):
                row = [pre.data[i][j] for j in range(self._out_dim)]
                sm = softmax(row)
                for j in range(self._out_dim):
                    da.data[i][j] = sm[j] - dout.data[i][j]
            dout = da

        act_fn, act_deriv = ACTIVATIONS[self.activation_name]
        pre = self._pre_act
        dpre = Matrix(batch, self._out_dim)
        for i in range(batch):
            for j in range(self._out_dim):
                dpre.data[i][j] = dout.data[i][j] * act_deriv(pre.data[i][j])

        self._dW = dpre.transpose() @ self._input  # (out, in)

        # bias gradient: sum over batch
        db = Matrix(self._out_dim, 1)
        for j in range(self._out_dim):
            s = sum(dpre.data[i][j] for i in range(batch))
            db.data[j][0] = s
        self._db = db

        dinput = dpre @ self.W  # (batch, in)
        return dinput

    def get_params(self):
        return [("W", self.W), ("b", self.b)]


# ── SGD Optimizer ───────────────────────────────────────────────────────────
class SGDOptimizer:
    def __init__(self, lr=0.01, momentum=0.9):
        self.lr = lr
        self.momentum = momentum
        self.velocities = {}

    def step(self, layers):
        for layer in layers:
            for name, param in layer.get_params():
                key = id(layer), name
                g = layer._dW if name == "W" else layer._db
                if key not in self.velocities:
                    self.velocities[key] = Matrix.zeros(g.rows, g.cols)
                v = self.velocities[key]
                v = v.mul_inplace(self.momentum).add_inplace(g)
                self.velocities[key] = v
                param.add_inplace(v.mul_inplace(-self.lr))


# ── Network ─────────────────────────────────────────────────────────────────
class Network:
    def __init__(self, layer_dims, activations=None):
        self.layers = []
        if activations is None:
            activations = ["relu"] * (len(layer_dims) - 2) + ["sigmoid"]
        for i in range(len(layer_dims) - 1):
            layer = Dense(layer_dims[i], layer_dims[i + 1], activations[i])
            self.layers.append(layer)

    def forward(self, X):
        out = X
        for layer in self.layers:
            out = layer.forward(out)
        return out

    def backward(self, dout):
        grad = dout
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def train_step(self, X, y, lr, momentum):
        out = self.forward(X)
        batch = X.rows
        diff = out.__sub__(y)
        dout = diff.mul_inplace(1.0 / batch)
        self.backward(dout)
        opt = SGDOptimizer(lr, momentum)
        opt.step(self.layers)
        loss = sum(sum((out.data[i][j] - y.data[i][j]) ** 2
                       for j in range(y.cols))
                   for i in range(y.rows)) / batch
        return loss

    def predict(self, X):
        return self.forward(X)


# ── Main: XOR ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    random.seed(42)

    X_data = [[0, 0], [0, 1], [1, 0], [1, 1]]
    y_data = [[0], [1], [1], [0]]

    X = Matrix(4, 2, X_data)
    y = Matrix(4, 1, y_data)

    net = Network([2, 8, 8, 1], activations=["relu", "relu", "sigmoid"])
    lr = 0.5
    momentum = 0.9
    epochs = 5000

    for epoch in range(1, epochs + 1):
        loss = net.train_step(X, y, lr, momentum)
        if epoch % 1000 == 0:
            preds = net.predict(X)
            correct = 0
            for i in range(4):
                pred_label = 1 if preds.data[i][0] > 0.5 else 0
                if pred_label == int(y_data[i][0]):
                    correct += 1
            print(f"Epoch {epoch:5d}  loss={loss:.4f}  accuracy={correct}/4")

    preds = net.predict(X)
    correct = 0
    for i in range(4):
        pred_label = 1 if preds.data[i][0] > 0.5 else 0
        if pred_label == int(y_data[i][0]):
            correct += 1
    print(f"\nFinal: {correct}/4 correct (accuracy={correct/4*100:.0f}%)")
    assert correct == 4, f"XOR not solved: {correct}/4"
