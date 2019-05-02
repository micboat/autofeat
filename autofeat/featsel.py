# -*- coding: utf-8 -*-
# Author: Franziska Horn <cod3licious@gmail.com>
# License: MIT

from __future__ import unicode_literals, division, print_function, absolute_import
from builtins import zip
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import sklearn.linear_model as lm


def select_features(df, target, df_scaled=False, max_it=100, eps=1e-16, verbose=0):
    """
    Inputs:
        - df: nxp pandas DataFrame with n data points and p features; to avoid overfitting, only provide data belonging
              to the n training data points. The variables should be scaled to have 0 mean and unit variance. If this is
              not the case, set df_scaled to False and it will be done for you.
        - target: n dimensional array with targets corresponding to the data points in df
        - df_scaled: whether df is already scaled to have 0 mean and unit variance (bool; default: False)
        - max_it: how many iterations will be performed at most (int; default: 100)
        - eps: eps parameter for LassoLarsCV regression model (float; default: 1e-16;
               might need to increase that to ~1e-8 or 1e-5 if you get a warning)
        - verbose: verbosity level (int; default: 0)
    Returns:
        - good_cols: list of column names for df with which a regression model can be trained
    """
    s = StandardScaler()
    # for performance reasons the scaled data can already be given
    if not df_scaled:
        # scale features to have 0 mean and unit std
        if verbose:
            print("[featsel] Scaling data...", end="")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = pd.DataFrame(s.fit_transform(df), columns=df.columns, dtype=np.float32)
        if verbose:
            print("done.")

    # split in training and test parts
    df_train = df[:max(3, int(0.8 * len(df)))]
    df_test = df[int(0.8 * len(df)):]
    target_train = target[:max(3, int(0.8 * len(df)))]
    target_test = target[int(0.8 * len(df)):]
    if not (len(df_train) == len(target_train) and len(df_test) == len(target_test)):
        raise ValueError("[featsel] df and target dimension mismatch.")

    # good cols contains the currently considered good features (=columns)
    good_cols = []
    best_cols = []
    # we want to select up to thr features (how much a regression model is comfortable with)
    thr = int(0.5 * df_train.shape[0])
    # our first target is the original target variable; later we operate on (target - predicted_target)
    new_target = target_train
    residual = np.mean(np.abs(target_test))
    last_residuals = np.zeros(max_it)
    smallest_residual = 10. * residual
    it = 0
    # we try optimizing features until we have converged or run over max_it
    while (it < max_it) and (not np.sum(np.isclose(residual, last_residuals)) >= 2):
        if verbose and not it % 10:
            print("[featsel] Iteration %3i; %3i selected features with residual: %.6f" % (it, len(good_cols), residual))
        last_residuals[it] = residual
        it += 1
        # select new possibly good columns from all but the currently considered good columns
        cols = set(df_train.columns)
        cols.difference_update(good_cols)
        cols_list = list(cols)
        # compute the absolute correlation of the (scaled) features with the (scaled) target variable
        w = np.abs(np.dot(s.fit_transform(new_target[:, None])[:, 0], df_train[cols_list].to_numpy()))
        # add promising features such that len(previous good cols + new cols) = thr
        good_cols.extend([cols_list[c] for c in np.argsort(w)[-(thr - len(good_cols)):]])
        # compute the regression residual based on the best features so far
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reg = lm.LassoLarsCV(eps=eps)
            X = df_train[good_cols].to_numpy()
            reg.fit(X, target_train)
        new_target = target_train - reg.predict(X)
        residual = np.mean(np.abs(target_test - reg.predict(df_test[good_cols].to_numpy())))
        # update the good columns based on the regression coefficients
        weights = dict(zip(good_cols, reg.coef_))
        good_cols = [c for c in weights if abs(weights[c]) > 1e-6]
        if residual < smallest_residual:
            smallest_residual = residual
            best_cols = [c for c in good_cols]
    if verbose:
        print("[featsel] Iteration %3i; %3i selected features with residual: %.6f  --> done." % (it, len(best_cols), smallest_residual))
    return best_cols
