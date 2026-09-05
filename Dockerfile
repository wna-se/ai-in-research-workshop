FROM python:3.12-alpine

RUN apk add --no-cache imagemagick

COPY svg_raster_optimize.py /app/svg_raster_optimize.py
RUN chmod +x /app/svg_raster_optimize.py

WORKDIR /work
ENTRYPOINT ["python3", "/app/svg_raster_optimize.py"]