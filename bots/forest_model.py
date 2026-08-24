import json

import numpy as np

from bots.neural_model import ACTIONS, MIN_TRAINING_SAMPLES, build_training_dataset, feature_vector  # noqa: F401

# feature_vector is re-exported so bots.engine can import both AI models' inference
# helpers from a single place per model, mirroring neural_model's own API shape.

N_TREES = 25
MAX_DEPTH = 5
MIN_SAMPLES_SPLIT = 10
MIN_SAMPLES_LEAF = 5
FEATURE_SAMPLE_RATIO = 0.7  # each split only considers a random subset of features (bagging's other half)
N_THRESHOLD_CANDIDATES = 8  # quantile cut points tried per feature, not every unique value -- keeps a year of data fast


def _gini(labels):
    if len(labels) == 0:
        return 0.0

    counts = np.bincount(labels, minlength=len(ACTIONS))
    probs = counts / len(labels)
    return 1.0 - float(np.sum(probs**2))


def _best_split(X, y, feature_indices):
    best_gain = 0.0
    best_feature = None
    best_threshold = None
    parent_impurity = _gini(y)
    n = len(y)

    for feature_index in feature_indices:
        column = X[:, feature_index]
        quantile_points = np.linspace(0, 1, N_THRESHOLD_CANDIDATES + 2)[1:-1]
        thresholds = np.unique(np.quantile(column, quantile_points))

        for threshold in thresholds:
            left_mask = column <= threshold
            n_left = int(left_mask.sum())
            n_right = n - n_left

            if n_left < MIN_SAMPLES_LEAF or n_right < MIN_SAMPLES_LEAF:
                continue

            left_impurity = _gini(y[left_mask])
            right_impurity = _gini(y[~left_mask])
            weighted_impurity = (n_left / n) * left_impurity + (n_right / n) * right_impurity
            gain = parent_impurity - weighted_impurity

            if gain > best_gain:
                best_gain = gain
                best_feature = int(feature_index)
                best_threshold = float(threshold)

    return best_feature, best_threshold, best_gain


def _leaf(y):
    counts = np.bincount(y, minlength=len(ACTIONS))
    total = counts.sum()
    probs = counts / total if total else np.ones(len(ACTIONS)) / len(ACTIONS)
    return {"leaf": True, "probs": probs}


def _build_tree(X, y, depth, rng):
    if depth >= MAX_DEPTH or len(y) < MIN_SAMPLES_SPLIT or len(np.unique(y)) == 1:
        return _leaf(y)

    n_features = X.shape[1]
    n_sample_features = max(1, int(round(n_features * FEATURE_SAMPLE_RATIO)))
    feature_indices = rng.choice(n_features, size=n_sample_features, replace=False)

    feature, threshold, gain = _best_split(X, y, feature_indices)

    if feature is None or gain <= 0:
        return _leaf(y)

    left_mask = X[:, feature] <= threshold
    right_mask = ~left_mask

    return {
        "leaf": False,
        "feature": feature,
        "threshold": threshold,
        "left": _build_tree(X[left_mask], y[left_mask], depth + 1, rng),
        "right": _build_tree(X[right_mask], y[right_mask], depth + 1, rng),
    }


def _predict_tree(tree, x):
    node = tree

    while not node["leaf"]:
        node = node["left"] if x[node["feature"]] <= node["threshold"] else node["right"]

    return node["probs"]


def train_forest(features, labels, n_trees=N_TREES, seed=11):
    rng = np.random.default_rng(seed)
    n = len(labels)
    trees = []

    for _ in range(n_trees):
        bootstrap_idx = rng.integers(0, n, size=n)
        tree = _build_tree(features[bootstrap_idx], labels[bootstrap_idx], depth=0, rng=rng)
        trees.append(tree)

    return {"trees": trees}


def predict_proba(forest, features):
    probs_sum = np.zeros(len(ACTIONS))

    for tree in forest["trees"]:
        probs_sum += _predict_tree(tree, features)

    return probs_sum / len(forest["trees"])


def predict(forest, features):
    probs = predict_proba(forest, features)
    predicted_index = int(np.argmax(probs))
    return ACTIONS[predicted_index], float(probs[predicted_index])


def train_symbol_model(history_df):
    features, labels = build_training_dataset(history_df)

    if len(features) < MIN_TRAINING_SAMPLES:
        return None

    return train_forest(features, labels)


def _tree_to_json(tree):
    if tree["leaf"]:
        return {"leaf": True, "probs": tree["probs"].tolist()}

    return {
        "leaf": False,
        "feature": tree["feature"],
        "threshold": tree["threshold"],
        "left": _tree_to_json(tree["left"]),
        "right": _tree_to_json(tree["right"]),
    }


def _tree_from_json(payload):
    if payload["leaf"]:
        return {"leaf": True, "probs": np.array(payload["probs"], dtype=float)}

    return {
        "leaf": False,
        "feature": payload["feature"],
        "threshold": payload["threshold"],
        "left": _tree_from_json(payload["left"]),
        "right": _tree_from_json(payload["right"]),
    }


def forest_to_json(forest):
    return {"trees": [_tree_to_json(tree) for tree in forest["trees"]]}


def forest_from_json(payload):
    return {"trees": [_tree_from_json(tree) for tree in payload["trees"]]}


def save_all_forests(forests_by_symbol, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {symbol: forest_to_json(forest) for symbol, forest in forests_by_symbol.items() if forest}

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file)


def load_all_forests(path):
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    return {symbol: forest_from_json(data) for symbol, data in payload.items()}
