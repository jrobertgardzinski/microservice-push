# Push channel — Python stdlib only, no dependencies. Stub-sends unless PUSH_PROVIDER is set.
FROM python:3.14-slim
WORKDIR /app
COPY server.py .
# Drop root, like the image encoder this service is modelled on. The divergence was an
# oversight, not a decision — and this is the layer the header-injection fix above lives in.
RUN useradd --system --no-create-home push
USER push
EXPOSE 8089
CMD ["python", "server.py"]
