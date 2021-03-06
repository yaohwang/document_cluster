# encoding: utf-8

import os
import sys
import traceback

from flask import Blueprint
from flask import request
from .service import predict


ads_bp = Blueprint('ads', __name__)


def parse_params(params):
    return (params['texts'], )


def parse_result(params, result):
    r = {}
    r['is_ads'] = result
    if params.get('texts_sendback', 1): r['texts'] = params['texts']
    return r


def callback(status, message, result):
    return {
               'status' : status,
               'message': message,
               'result' : result
           }


@ads_bp.route('/nlp/v2/detect/ads', methods=['POST'])
def detect_ads():
    status  = 0
    message = ''
    result  = {}

    try:
        """
        {
            "texts" : ['测试', ...],
            "texts_sendback" : 1,
        }
        """
        params = request.get_json()

        result = parse_result(params, predict(*parse_params(params)))
        return callback(status, message, result)

    except:
        # callback
        status  = 1
        message = traceback.format_exc()
        print(message)
        return callback(status, '', result)
