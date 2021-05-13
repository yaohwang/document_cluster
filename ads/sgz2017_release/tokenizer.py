# encoding: utf-8

import re
import dill
import pickle
import unicodedata

from time import time
from itertools import chain
from itertools import zip_longest
from sklearn.feature_extraction.text import TfidfVectorizer

def is_special(i):
    is_1 =  i in ['<unk>', '<loc>', '<contact>', '<recruit>', '<corpus>', '<colonel>']
    is_2 = bool(re.match(r'^<num-[0-9]+>$', i))
    return is_1 or is_2


def not_special(i):
    return not is_special(i)


def __replace(s):
    if is_special(s): return s
    
    # 微信
    s = s.replace('威', '微')
    s = s.replace('徽', '微')
    s = s.replace('徵', '微')
    s = s.replace('亻言', '信')
    
    s = s.replace('微新', '微信')
    s = s.replace('微信', '微')
    
    # 加
    s = s.replace('咖', '加')
    s = s.replace('架', '加')
    s = s.replace('嫁', '加')
    s = s.replace('十', '加')
    s = s.replace('茄', '加')
    s = s.replace('迦', '加')
    
    s = s.replace('加下', '加')
    s = s.replace('加一下', '加')
    
    s = s.replace('加', '+')
    
    # 收人
    s = s.replace('活人', '人')
    # s = s.replace('收人', '<recruit>')
    
    # 团长
    s = s.replace('圕', '团')
    
    # 充
    s = s.replace('冲', '充')
    s = s.replace('直充', '充')
    
    # 出
    s = s.replace('础', '出')

    # 卖
    s = s.replace('麦', '出')
    
    return s


def replace(x):
    return [__replace(i) for i in x]


def split_regex(s, reg, flag):
    r = re.split(reg, s)
    if 1 >= len(r): return r
    r = list(chain.from_iterable(zip_longest(r[:-1], [], fillvalue=flag))) + r[-1:]
    return [i for i in r if i]


def split_location(s):
    return split_regex(s, r'{localization:[0-9]+\-[0-9]+}', '<loc>')


def __split_terminology(s, term, flag):
    if is_special(s): return [s]
    return split_regex(s, r'%s' % term, flag)


def split_terminology(x, term, flag):
    return list(chain.from_iterable([__split_terminology(i, term, flag) for i in x]))


def __split_charnum(s):
    if is_special(s): return [s]
    return [c for c in re.split(r'([0-9a-z]+)', s) if c]


def split_charnum(x):
    return list(chain.from_iterable([__split_charnum(s) for s in x]))


def is_numeric(s):
    has_num = bool(re.findall(r'[0-9]+', s))
    hasnot_other = not bool(re.findall(r'[^0-9]+', s))
    return has_num and hasnot_other


def convert_num(x):
    return ['<num-%s>' % len(i) if not_special(i) and is_numeric(i) else i for i in x]


def is_charnum(s):
    has_num = bool(re.findall(r'[0-9]+', s))
    has_char = bool(re.findall(r'[a-z]+', s))
    hasnot_other = not bool(re.findall(r'[^a-z0-9]+', s))
    return has_num and has_char and hasnot_other


def is_v_num(s):
    return bool(re.match(r'v[0-9]+', s))


def is_vx_num(s):
    return bool(re.match(r'vx[0-9]+', s))


def is_qq_num(s):
    return bool(re.match(r'qq[0-9]+', s))


def __convert_chars_numbers(s):
    if is_special(s): return [s]
    if is_v_num(s): return ['微', '<contact>']
    if is_vx_num(s): return ['微', '<contact>']
    if is_qq_num(s): return ['微', '<contact>']
    if is_charnum(s): return ['<contact>']
    return [s]
    

def convert_chars_numbers(x):
    return list(chain.from_iterable([__convert_chars_numbers(s) for s in x]))


def __split_normal_special(s):
    if is_special(s): return s, ''
    return ''.join(re.findall(r'[,\+a-z0-9\u4e00-\u9fa5]+', s)), ''.join(re.findall(r'[^,\+a-z0-9\u4e00-\u9fa5]+', s))


def split_normal_special(x):
    r = [__split_normal_special(i) for i in x]
    r1, r2 = zip(*r)
    r1 = [i for i in r1 if i]
    r2 = [i for i in r2 if i]
    return r1, r2


def __split_once(s):
    if is_special(s): return [s]
    r = list(s)
    return r


def split_once(x):
    return list(chain.from_iterable([__split_once(s) for s in x]))


stopwords1_usual = ['你', '我', '他', '她', '它', '们',
                    '吧', '吗', '嘛', '啊', '阿', '呢', '呀',
                    '的', '地', 
                    '怎', '么',
                    '那', '哪',
                    '就', '没', '了', '谢', '配', '合']


stopwords1 = stopwords1_usual
stopwords = stopwords1

def filter_stopwords(x):
    return [i for i in x if i not in stopwords]


def split1(s):
    s = s.replace(' ', '')
    s = s.lower()
    s = unicodedata.normalize('NFKC', s)
    
    tokens = split_location(s)
    
    tokens, tokens_special = split_normal_special(tokens)
    
    tokens = split_charnum(tokens)
    tokens = convert_num(tokens)
    tokens = convert_chars_numbers(tokens)
    
    tokens = replace(tokens)
    
    tokens = split_terminology(tokens, '收人', '<recruit>')
    tokens = split_terminology(tokens, '军团', '<corpus>')
    tokens = split_terminology(tokens, '团长', '<colonel>')
    tokens = split_once(tokens)
    
    tokens = filter_stopwords(tokens)
    
    tokens += ['<special-char>'] * len(''.join(tokens_special))
    return tokens


from .dataset import X_train
vectorizer = TfidfVectorizer(sublinear_tf=True, min_df=1e-3, tokenizer=split1)
tfidf = vectorizer.fit_transform(X_train)
feature_names = vectorizer.get_feature_names()

def low_freq(x):
    return ['<unk>' if i not in feature_names else i for i in x]


def split2(s):
    tokens = split1(s)
    tokens = low_freq(tokens)
    return tokens