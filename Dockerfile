# Push channel — Python stdlib only, no dependencies. Stub-sends unless PUSH_PROVIDER is set.
FROM python:3.12-slim
WORKDIR /app
COPY server.py .
EXPOSE 8089
CMD ["python", "server.py"]
