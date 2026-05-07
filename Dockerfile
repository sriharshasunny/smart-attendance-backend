# Python 3.9 has a pre-compiled dlib wheel on PyPI (manylinux)
# This avoids the 8GB RAM compilation issue entirely
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Only minimal system libs needed at runtime (not for compilation)
RUN apt-get update && apt-get install -y \
    libstdc++6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

# Install dlib first — pip will download the pre-built wheel for Python 3.9 Linux
RUN pip install --no-cache-dir dlib

# Install face_recognition which depends on dlib already being installed
RUN pip install --no-cache-dir face_recognition

# Install the rest of the app dependencies
RUN pip install --no-cache-dir \
    Flask \
    Flask-Cors \
    "pymongo[srv]" \
    certifi \
    python-dotenv \
    opencv-python-headless \
    gunicorn

COPY . .

# Use Render's PORT env variable
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --timeout 120 --workers 1 app:app"]
