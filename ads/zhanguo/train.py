# encoding: utf-8

import dill
import scipy
import numpy as np
import lightgbm as lgb

from typing import Union, Optional, Dict, List, Tuple, Any
from pathlib import Path
from collections import Counter
from logger import logging
logger = logging.getLogger(__name__)

from sklearn import metrics
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer

from tokenizer import tokenize
from service import predict
from rule import rule, is_suspect

Model = Any
ModelEmbedding = Any


def fit_embedding_tfidf(
    X: List[str],
    tokenizer=lambda x: x
) -> Tuple[scipy.sparse.csr_matrix, ModelEmbedding]:
    # TODO: params
    embedding = TfidfVectorizer(lowercase=False, sublinear_tf=True, tokenizer=tokenizer)
    X_ = embedding.fit_transform(X)
    return X_, embedding


def fit_lgb(
    X: List[str],
    y: List[int],
    **params
) -> Model:
    num_round = params.pop('num_round', 1000)
    model = lgb.train(params, lgb.Dataset(X, label=y), num_round)
    return model


def fit(
    X: List[str],
    y: List[int],
    save_directory: Optional[str] = None,
    filename_prefix: Optional[str] = None,
    embedding_type: str = 'tfidf',
    model_type: str = 'lgb',
    params: Dict = {}
):

    def rule_split(
        X: List[str],
        y: List[int]
    ) -> Tuple[List[str], List[int], List[str], List[int]]:

        y_pred = [rule(x) for x in X]
        X_rest, y_rest = zip(*[[X[i], y[i]] for i, _ in enumerate(y_pred) if _ is None])
        logger.info(f'rule, {len(y)-len(y_rest)}')

        y_temp = [is_suspect(x) for x in X_rest]
        X_suspect, y_suspect = zip(*[[X_rest[i], y_rest[i]] for i, _ in enumerate(y_temp) if _])
        X_normal, y_normal = zip(*[[X_rest[i], y_rest[i]] for i, _ in enumerate(y_temp) if not _])
        return X_suspect, list(y_suspect), X_normal, list(y_normal)

    def fit_model(
        X: List[str],
        y: List[int],
        **params
    ) -> Tuple[ModelEmbedding, Model]:
        if 'tfidf' == embedding_type:
            X, model_embedding = fit_embedding_tfidf(X)
        if 'lgb' == model_type:
            model = fit_lgb(X, y, **params)
        return model_embedding, model

    def save_model(
        model_embedding: ModelEmbedding,
        model: Model,
        save_directory: str,
        filename_prefix: Optional[str] = None
    ):
        path = Path(save_directory)
        filename_prefix = filename_prefix if filename_prefix else 'last'
        name = 'ads-%s.mdl' % filename_prefix
        model.save_model((path/name).as_posix())
        name = 'embedding-%s.mdl' % filename_prefix
        with (path/name).open('wb') as f:
            dill.dump(model_embedding, f)

    X = [tokenize(x) for x in X]
    X_suspect, y_suspect, X_normal, y_normal = rule_split(X, y)
    logger.info(f'suspect, {Counter(y_suspect)}')
    logger.info(f' normal, {Counter(y_normal)}')

    model_embedding_1, model_1 = fit_model(X_suspect, y_suspect, **params)
    if save_directory:
        save_model(model_embedding_1, model_1, save_directory, filename_prefix='1-last')

    model_embedding_2, model_2 = fit_model(X_normal, y_normal, **params)
    if save_directory:
        save_model(model_embedding_2, model_2, save_directory, filename_prefix='2-last')

    return model_embedding_1, model_1, model_embedding_2, model_2


def evaluate(
    X: List[str],
    y: List[int],
    model_embedding_1: ModelEmbedding,
    model_1: Model,
    model_embedding_2: ModelEmbedding,
    model_2: Model
):
    y_pred = predict(X, model_embedding_1, model_1, model_embedding_2, model_2)
    print(metrics.classification_report(y, y_pred, digits=3))

    X_tokens = [tokenize(x) for x in X]
    for x, x_tokens, _y, _y_pred in zip(X, X_tokens, y, y_pred):
        if _y != _y_pred:
            print(f'text: {x}\n tokens: {x_tokens}\n y: {_y}\n y pred: {_y_pred}\n')
            print()
        


def fit_evalute(
    X: List[str],
    y: List[str],
    save_directory: str,
    filename_prefix: Optional[str] = None,
    test_size: float = 0.3,
    random_state: int = 42,
    params: Dict = {}
):
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        stratify = y,
        test_size = test_size,
        random_state = random_state
    )

    logger.info(f'train shape=({len(X_train)},)')
    logger.info(f' test shape=({len(X_test)},)')

    logger.info('fitting')
    model_embedding_1, model_1, model_embedding_2, model_2 = fit(X_train, y_train, params=params)

    logger.info('train evalute')
    evaluate(X_train, y_train, model_embedding_1, model_1, model_embedding_2, model_2)

    logger.info('test evaluate')
    evaluate(X_test, y_test, model_embedding_1, model_1, model_embedding_2, model_2)

    logger.info('re-fitting')
    fit(X, y, save_directory=save_directory, filename_prefix=filename_prefix, params=params)


if __name__ == '__main__':
    from dataset import X, y
    params = {'num_leaves': 2**5-1, 'objective': 'multiclass', 'num_class': 3, 'num_round': 1000, 'verbose': -1}
    fit_evalute(X, y, save_directory='./model', params=params)