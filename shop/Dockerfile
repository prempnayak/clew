# Nebula Gear, the store under test. Build context: the repo root's shop/ folder.
FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "fastapi>=0.141" "uvicorn>=0.54" "jinja2>=3.1" "python-multipart>=0.0.32"
COPY . ./shop
RUN rm -f ./shop/planted_bugs.yaml
ENV SHOP_DB=/srv/data/nebula.db
EXPOSE 8090
CMD ["uvicorn", "shop.app:app", "--host", "0.0.0.0", "--port", "8090"]
