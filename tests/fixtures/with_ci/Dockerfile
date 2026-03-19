FROM python:3.12-slim

WORKDIR /app

ENV APP_ENV=production
ENV LOG_LEVEL=info

RUN apt-get update && apt-get install -y git curl

COPY . .
RUN pip install -e .

EXPOSE 8080

CMD ["python", "-m", "app"]
