from . import main
from flask import render_template


@main.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')
