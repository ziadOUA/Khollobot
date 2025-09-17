FROM python:3.12-slim-bullseye

WORKDIR /khollobot

COPY . .

RUN pip3 install --no-cache-dir --upgrade pip

RUN pip3 install --no-cache-dir -r requirements.txt

VOLUME /khollobot

