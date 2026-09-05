FROM python:3.12-alpine

RUN apk add --no-cache imagemagick imagemagick-jpeg imagemagick-webp

COPY svg_raster_optimize.py /app/svg_raster_optimize.py
RUN chmod +x /app/svg_raster_optimize.py

WORKDIR /work
ENTRYPOINT ["python3", "/work/svg_raster_optimize.py"]
