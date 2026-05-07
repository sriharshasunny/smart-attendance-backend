# Use a base image that has dlib + face_recognition PRE-COMPILED
# This avoids 8GB+ memory usage during build from compiling dlib from source
FROM animcogn/face_recognition:cpu

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install only our additional Python dependencies (dlib/face_recognition already installed)
COPY requirements.txt /app/
RUN pip install --upgrade pip --no-cache-dir
RUN pip install Flask Flask-Cors "pymongo[srv]" certifi python-dotenv opencv-python-headless gunicorn --no-cache-dir

# Copy project
COPY . /app/

# Expose port
EXPOSE 5000

# Run gunicorn
# Run gunicorn using Render's dynamic PORT environment variable
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 120 --workers 1 app:app"]
