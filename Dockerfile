# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY *.py .

# Install uv for faster dependency installation
RUN pip install --no-cache-dir uv

# Install dependencies using uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Create a non-root user for security
RUN useradd -m -u 1000 watchdog && \
    chown -R watchdog:watchdog /app

USER watchdog

# Run the main script
CMD ["python", "-u", "main.py"]
