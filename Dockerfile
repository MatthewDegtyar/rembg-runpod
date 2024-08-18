from python:3.11.1-buster

WORKDIR /

COPY builder/req.txt .
RUN pip install -r req.txt

COPY builder/handler.py .

CMD [ "python", "-u", "handler.py" ]