FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /usr/src/app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Define build arguments
ARG BASE_ENDPOINT
ARG OPIK_API_KEY
ARG OPIK_WORKSPACE

# Use build arguments to update .env file
RUN sed -i 's|__base_endpoint__|'"$BASE_ENDPOINT"'|' agent_config.yaml
RUN sed -i 's|__OPIK_API_KEY__|'"$OPIK_API_KEY"'|' .env
RUN sed -i 's|__OPIK_WORKSPACE__|'"$OPIK_WORKSPACE"'|' .env

RUN mkdir -p /var/log/agentcontainer

RUN chmod -R 755 /var/log/agentcontainer

# Make port 7009 available to the world outside this container
EXPOSE 7009

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7009"]

