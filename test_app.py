from flask import Flask
import json
import pytest

from app import app



def test_index():
    response = app.test_client().get('/')
    assert response.status_code == 200


def test_submit():
    response = app.test_client().post('/submit', data=dict(
        twitchuser="test"
    ))
    assert response.status_code == 200


def test_submit__failure__redirect():
    response = app.test_client().post('/submit', data=dict(twitchuser=''
    ))
    assert response.status_code == 200


def test_follows():
    response = app.test_client().post('/follow', data=dict(
        login='test'
    ))
    assert response.status_code == 200