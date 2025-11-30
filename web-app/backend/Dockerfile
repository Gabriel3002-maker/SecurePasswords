FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for some python packages like cryptography/paramiko)
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app ./app


# Create volume directory for database
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run command
CMD ["uvicorn", "main:app", "--app-dir", "app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
