# Use miniconda3 - conda has pre-compiled dlib binaries (no compilation needed!)
FROM continuumio/miniconda3:latest

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dlib via conda - guaranteed pre-compiled binary, ZERO compilation
RUN conda install -c conda-forge dlib -y && conda clean -afy

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install face_recognition and all other dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use Render's PORT env variable
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --timeout 120 --workers 1 app:app"]

