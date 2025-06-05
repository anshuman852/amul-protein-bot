FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run as non-root user
RUN useradd -m botuser

# Create data directory and set permissions
RUN mkdir -p data && chown -R botuser:botuser /app

USER botuser

# Command to run the bot
CMD ["python", "bot.py"]
