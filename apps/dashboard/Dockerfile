FROM python:3.12-slim
WORKDIR /app
COPY public ./public
EXPOSE 3000
CMD ["python", "-m", "http.server", "3000", "--directory", "public"]
